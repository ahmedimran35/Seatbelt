#!/usr/bin/env python3
"""Prepare and execute reversible actions for Seatbelt.

Usage:
    python3 scripts/undo.py prepare --blast <id> [--db path] [--terraform-plan path]
    python3 scripts/undo.py execute <token> [--approval yes|GO]
    python3 scripts/undo.py list
    python3 scripts/undo.py check <token>
    python3 scripts/undo.py prune --older-than 7d
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from blast import sha256_file  # noqa: E402
from receipt import append as append_receipt  # noqa: E402

HOME = Path(os.getenv("SEATBELT_HOME", str(Path.home() / ".seatbelt")))
BLASTS = HOME / "blasts"
UNDOS = HOME / "undos"
SECRET_RE = re.compile(r"(?:^|/)\.env(?:\..+)?$|/\.ssh/|id_rsa|/credentials", re.IGNORECASE)


def git(*args: str, cwd: str | None = None) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False, cwd=cwd
        )
    except OSError:
        return 1, ""
    return result.returncode, result.stdout.strip()


def load_blast(ref: str) -> dict[str, Any]:
    path = Path(ref)
    if not path.exists():
        path = BLASTS / f"{ref}.json"
    if not path.exists():
        raise SystemExit(f"seatbelt: no blast card {ref!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(token: str) -> dict[str, Any]:
    path = UNDOS / f"{token}.json"
    if not path.exists():
        raise SystemExit(f"seatbelt: no undo token {token!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(manifest: dict[str, Any]) -> None:
    UNDOS.mkdir(parents=True, exist_ok=True)
    (UNDOS / f"{manifest['token']}.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def prepare_trash(card: dict[str, Any], token: str) -> dict[str, Any]:
    root = UNDOS / token / "files"
    entries = []
    secrets = False
    for target in card["targets"]:
        if target["kind"] != "path":
            continue
        source = Path(target["path"])
        if not source.exists():
            continue
        relative = target.get("relative") or os.path.relpath(source, card["cwd"])
        stored = "abs/" + relative.lstrip("/") if Path(relative).is_absolute() else relative
        backup = root / stored
        backup.parent.mkdir(parents=True, exist_ok=True)
        mode = oct(source.stat().st_mode & 0o777)
        digest = sha256_file(source) if source.is_file() else None
        if SECRET_RE.search(str(source)):
            secrets = True
        if source.is_dir():
            shutil.copytree(source, backup, dirs_exist_ok=True)
        else:
            shutil.copy2(source, backup)
        entries.append({
            "path": str(source), "relative": relative, "backup": str(backup),
            "sha256": digest, "is_dir": source.is_dir() or not digest, "mode": mode,
        })
    if not entries:
        raise SystemExit("seatbelt: no existing path targets to prepare")
    return {
        "strategy": "trash",
        "entries": entries,
        "expect": {"backups_intact": True},
        "reverse": {"type": "restore_paths"},
        "contains_secrets": secrets,
    }


def prepare_git_ref(card: dict[str, Any], token: str) -> dict[str, Any]:
    code, ref = git("rev-parse", "--abbrev-ref", "HEAD", cwd=card["cwd"])
    if code != 0 or not ref:
        raise SystemExit("seatbelt: cannot determine current branch")
    code, sha = git("rev-parse", "HEAD", cwd=card["cwd"])
    tag = f"seatbelt/{token}"
    code, _ = git("tag", tag, sha, cwd=card["cwd"])
    if code != 0:
        raise SystemExit("seatbelt: could not create backup tag")
    stash = None
    code, dirty = git("status", "--porcelain", cwd=card["cwd"])
    if code == 0 and dirty:
        git("stash", "push", "-u", "-m", f"seatbelt:{token}", cwd=card["cwd"])
        code, listing = git("stash", "list", "--format=%gd %H", cwd=card["cwd"])
        if code == 0 and listing:
            stash = listing.splitlines()[0].split()[0]
    return {
        "strategy": "git-ref",
        "ref": ref, "sha": sha, "tag": tag, "stash": stash,
        "expect": {"tag_exists": True},
        "reverse": {"type": "restore_ref"},
        "contains_secrets": False,
    }


def prepare_force_push(card: dict[str, Any], token: str) -> dict[str, Any]:
    branch = None
    for target in card["targets"]:
        if target["kind"] == "git-ref":
            branch = target["ref"]
            break
    if not branch:
        match = re.search(r"git\s+push\b[^\\n]*\b([A-Za-z0-9_./-]+)\s*$", card["command"])
        branch = match.group(1) if match else None
    if not branch:
        raise SystemExit("seatbelt: cannot identify branch for force-push")
    code, output = git("ls-remote", "origin", f"refs/heads/{branch}", cwd=card["cwd"])
    remote_sha = output.split()[0] if code == 0 and output else ""
    if not remote_sha:
        raise SystemExit("seatbelt: cannot read remote ref; refusing to prepare")
    code, local_sha = git("rev-parse", "HEAD", cwd=card["cwd"])
    if code != 0 or not local_sha:
        raise SystemExit("seatbelt: cannot read local HEAD; refusing to prepare")
    tag = f"seatbelt/{token}"
    code, _ = git("tag", tag, remote_sha, cwd=card["cwd"])
    if code != 0:
        raise SystemExit("seatbelt: could not create backup tag")
    return {
        "strategy": "force-push", "branch": branch, "remote": "origin",
        "remote_sha": remote_sha, "expected_post_sha": local_sha, "tag": tag,
        "expect": {"remote_at_post_state": True},
        "reverse": {"type": "restore_remote_ref"},
        "contains_secrets": False,
    }


def prepare_sql(card: dict[str, Any], token: str, db: str | None) -> dict[str, Any]:
    if not db:
        raise SystemExit("seatbelt: sql-backup requires --db <sqlite-file>")
    match = re.search(
        r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([A-Za-z0-9_]+)", card["command"], re.IGNORECASE
    )
    if not match:
        raise SystemExit("seatbelt: cannot identify table name")
    table = match.group(1)
    suffix = re.sub(r"[^A-Za-z0-9_]", "_", token)
    backup = f"seatbelt_{suffix}_{table}"
    connection = sqlite3.connect(db)
    try:
        exists = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        if not exists:
            raise SystemExit(f"seatbelt: table {table} does not exist in {db}")
        rows = connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        connection.execute(f'CREATE TABLE "{backup}" AS SELECT * FROM "{table}"')
        connection.commit()
    finally:
        connection.close()
    return {
        "strategy": "sql-backup", "db": db, "table": table, "backup_table": backup,
        "rows": rows,
        "expect": {"backup_rows": rows},
        "reverse": {"type": "restore_sql_table"},
        "contains_secrets": False,
    }


def prepare_terraform(card: dict[str, Any], token: str, plan: str | None) -> dict[str, Any]:
    root = UNDOS / token / "state"
    files = []
    for name in glob.glob("*.tfstate*", root_dir=card["cwd"]):
        source = Path(card["cwd"]) / name
        backup = root / name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)
        files.append({"path": str(source), "backup": str(backup), "sha256": sha256_file(source)})
    if not files:
        raise SystemExit("seatbelt: no terraform state files found")
    plan_copy = None
    if plan:
        source = Path(plan)
        backup = root / "plan"
        shutil.copy2(source, backup)
        plan_copy = str(backup)
    return {
        "strategy": "terraform", "files": files, "plan": plan_copy,
        "expect": {"state_unchanged": True},
        "reverse": {"type": "restore_terraform_state"},
        "contains_secrets": True,  # state can contain secrets
    }


def do_prepare(args: argparse.Namespace) -> int:
    card = load_blast(args.blast)
    token = card["token"]
    strategy = card["strategy"]
    if card.get("tier", 0) >= 4:
        raise SystemExit("seatbelt: T4 actions are denied; no undo token is issued")
    if strategy == "none":
        raise SystemExit("seatbelt: no undo strategy for this command; refusing to prepare")
    if (UNDOS / f"{token}.json").exists():
        raise SystemExit(f"seatbelt: undo token {token} already exists")

    if strategy == "trash":
        detail = prepare_trash(card, token)
    elif strategy == "git-ref":
        detail = prepare_git_ref(card, token)
    elif strategy == "force-push":
        detail = prepare_force_push(card, token)
    elif strategy == "sql-backup":
        detail = prepare_sql(card, token, args.db)
    elif strategy == "terraform":
        detail = prepare_terraform(card, token, args.terraform_plan)
    else:
        raise SystemExit(f"seatbelt: unknown strategy {strategy}")

    manifest = {
        "token": token,
        "created": datetime.now(timezone.utc).isoformat(),
        "expires": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "blast_id": card["id"], "command": card["command"], "tier": card["tier"],
        "cwd": card["cwd"], **detail,
    }
    save_manifest(manifest)
    print(f"Undo token: {token}")
    print(f"Strategy: {strategy}")
    if detail.get("contains_secrets"):
        print("WARNING: backup contains potentially secret data; stored with mode 0700")
    (UNDOS / token).mkdir(parents=True, exist_ok=True)
    os.chmod(UNDOS / token, 0o700)
    return 0


def verify_prestate(manifest: dict[str, Any]) -> tuple[bool, str]:
    strategy = manifest["strategy"]
    if strategy == "trash":
        for entry in manifest["entries"]:
            backup = Path(entry["backup"])
            if not backup.exists():
                return False, f"backup missing: {backup}"
            if entry["sha256"] and sha256_file(backup) != entry["sha256"]:
                return False, f"backup changed: {backup}"
            original = Path(entry["path"])
            if original.exists() and entry["sha256"] and sha256_file(original) != entry["sha256"]:
                return False, f"destination has different content: {original}"
    elif strategy == "git-ref":
        code, _ = git("rev-parse", "--verify", "--quiet", manifest["tag"], cwd=manifest["cwd"])
        if code != 0:
            return False, "backup tag missing"
    elif strategy == "force-push":
        code, output = git(
            "ls-remote", manifest["remote"], f"refs/heads/{manifest['branch']}", cwd=manifest["cwd"]
        )
        current = output.split()[0] if code == 0 and output else ""
        if current != manifest.get("expected_post_sha", manifest["remote_sha"]):
            return False, "remote is not at the expected post-action state; refusing to overwrite other work"
        code, _ = git("rev-parse", "--verify", "--quiet", manifest["tag"], cwd=manifest["cwd"])
        if code != 0:
            return False, "backup tag missing"
    elif strategy == "sql-backup":
        connection = sqlite3.connect(manifest["db"])
        try:
            rows = connection.execute(
                f'SELECT count(*) FROM "{manifest["backup_table"]}"'
            ).fetchone()[0]
        finally:
            connection.close()
        if rows != manifest["rows"]:
            return False, "backup table row count changed"
    elif strategy == "terraform":
        for item in manifest["files"]:
            if sha256_file(item["path"]) != item["sha256"]:
                return False, f"state changed: {item['path']}"
    return True, ""


def restore(manifest: dict[str, Any], apply_plan: bool) -> tuple[bool, str]:
    strategy = manifest["strategy"]
    notes = []
    if strategy == "trash":
        for entry in manifest["entries"]:
            original = Path(entry["path"])
            original.parent.mkdir(parents=True, exist_ok=True)
            if original.exists():
                if entry["sha256"] and sha256_file(original) == entry["sha256"]:
                    notes.append(f"already restored: {original}")
                    continue
                return False, f"refusing to overwrite: {original}"
            shutil.move(entry["backup"], str(original))
    elif strategy == "git-ref":
        code, out = git("update-ref", f"refs/heads/{manifest['ref']}", manifest["sha"],
                        cwd=manifest["cwd"])
        if code != 0:
            return False, f"update-ref failed: {out}"
        if manifest.get("stash"):
            code, out = git("stash", "apply", manifest["stash"], cwd=manifest["cwd"])
            if code != 0:
                notes.append(f"stash apply failed: {out}")
            else:
                git("stash", "drop", manifest["stash"], cwd=manifest["cwd"])
    elif strategy == "force-push":
        code, out = git(
            "push", "--force-with-lease", manifest["remote"],
            f"{manifest['tag']}:refs/heads/{manifest['branch']}", cwd=manifest["cwd"],
        )
        if code != 0:
            return False, f"remote restore failed: {out}"
    elif strategy == "sql-backup":
        connection = sqlite3.connect(manifest["db"])
        try:
            connection.execute("BEGIN")
            connection.execute(f'DROP TABLE IF EXISTS "{manifest["table"]}"')
            connection.execute(
                f'ALTER TABLE "{manifest["backup_table"]}" RENAME TO "{manifest["table"]}"'
            )
            connection.commit()
            rows = connection.execute(
                f'SELECT count(*) FROM "{manifest["table"]}"'
            ).fetchone()[0]
            if rows != manifest["rows"]:
                notes.append(f"row count mismatch after restore: {rows}")
        finally:
            connection.close()
    elif strategy == "terraform":
        for item in manifest["files"]:
            shutil.copy2(item["backup"], item["path"])
        if manifest.get("plan"):
            if apply_plan:
                code, out = git("status", "--porcelain", cwd=manifest["cwd"])
                result = subprocess.run(
                    ["terraform", "apply", "-auto-approve", manifest["plan"]],
                    cwd=manifest["cwd"], capture_output=True, text=True, check=False,
                )
                if result.returncode != 0:
                    notes.append(f"terraform apply failed: {result.stderr.strip()}")
            else:
                notes.append("state copied back; run `terraform apply` yourself to reconcile")
    return True, "; ".join(notes)


def do_execute(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.token)
    if manifest.get("executed_at"):
        raise SystemExit(f"seatbelt: token {args.token} was already executed")
    ok, reason = verify_prestate(manifest)
    if not ok:
        print(f"seatbelt: undo refused — {reason}")
        append_receipt({
            "type": "undo", "command": f"undo {args.token}", "tier": 2,
            "mode": "full", "approval": args.approval, "undo_token": args.token,
            "verified": False, "notes": reason,
            "agent_id": os.getenv("SEATBELT_AGENT_ID", "unknown"),
        })
        return 3
    ok, notes = restore(manifest, args.apply_plan)
    manifest["executed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["restore_ok"] = ok
    save_manifest(manifest)
    append_receipt({
        "type": "undo", "command": f"undo {args.token}", "tier": 2,
        "mode": "full", "approval": args.approval, "undo_token": args.token,
        "verified": ok, "notes": notes,
        "agent_id": os.getenv("SEATBELT_AGENT_ID", "unknown"),
    })
    print(f"Undo {'completed' if ok else 'failed'} for {args.token}")
    if notes:
        print("Notes: " + notes)
    return 0 if ok else 3


def do_list() -> int:
    UNDOS.mkdir(parents=True, exist_ok=True)
    for path in sorted(UNDOS.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        status = "executed" if manifest.get("executed_at") else "available"
        print(f"{manifest['token']}  {manifest['strategy']:12s} {status:9s} {manifest['command']}")
    return 0


def do_check(token: str) -> int:
    manifest = load_manifest(token)
    ok, reason = verify_prestate(manifest)
    print(f"{token}: {'OK' if ok else 'BLOCKED'} ({reason or manifest['strategy']})")
    return 0 if ok else 3


def do_prune(days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    for path in sorted(UNDOS.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(manifest["created"])
        if created > cutoff:
            continue
        backup_dir = UNDOS / manifest["token"]
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        path.unlink()
        removed += 1
    print(f"Pruned {removed} undo manifest(s) older than {days} day(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--blast", required=True)
    prep.add_argument("--db", help="sqlite file for sql-backup")
    prep.add_argument("--terraform-plan", help="saved plan for terraform restore")

    execute = sub.add_parser("execute")
    execute.add_argument("token")
    execute.add_argument("--approval", default="confirmed", choices=["yes", "GO", "confirmed"])
    execute.add_argument("--apply-plan", action="store_true")

    sub.add_parser("list")
    check = sub.add_parser("check")
    check.add_argument("token")
    prune = sub.add_parser("prune")
    prune.add_argument("--older-than", type=int, default=7)

    args = parser.parse_args(argv)
    if args.action == "prepare":
        return do_prepare(args)
    if args.action == "execute":
        return do_execute(args)
    if args.action == "list":
        return do_list()
    if args.action == "check":
        return do_check(args.token)
    return do_prune(args.older_than)


if __name__ == "__main__":
    raise SystemExit(main())
