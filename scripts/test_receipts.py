#!/usr/bin/env python3
"""End-to-end tests for blast cards, undo tokens and receipts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
FAILURES: list[str] = []


def call(script: str, args: list[str], cwd: Path, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SEATBELT_HOME"] = str(home)
    env["SEATBELT_AGENT_ID"] = "test-agent"
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=cwd, env=env, capture_output=True, text=True, check=False,
    )


def git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def card(command: str, cwd: Path, home: Path, extra: list[str] | None = None) -> dict:
    result = call("blast.py", ["--command", command, "--save", "--format", "json", *(extra or [])],
                  cwd, home)
    if result.returncode != 0:
        raise AssertionError(f"blast failed for {command}: {result.stderr}")
    return json.loads(result.stdout)


def prepare(blast_id: str, cwd: Path, home: Path, extra: list[str] | None = None) -> str:
    result = call("undo.py", ["prepare", "--blast", blast_id, *(extra or [])], cwd, home)
    if result.returncode != 0:
        raise AssertionError(f"prepare failed: {result.stderr}")
    return result.stdout.split("Undo token: ", 1)[1].splitlines()[0].strip()


def execute(token: str, cwd: Path, home: Path, extra: list[str] | None = None) -> int:
    return call("undo.py", ["execute", token, "--approval", "yes", *(extra or [])],
                cwd, home).returncode


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def case_trash_file(tmp: Path) -> None:
    cwd, home = tmp / "p1", tmp / "h1"
    cwd.mkdir(); home.mkdir()
    target = cwd / "data.txt"
    target.write_text("important content\n")
    before = digest(target)
    c = card("rm data.txt", cwd, home)
    check("trash card tier", c["tier"] == 1, str(c["tier"]))
    check("trash strategy", c["strategy"] == "trash", c["strategy"])
    token = prepare(c["id"], cwd, home)
    target.unlink()
    check("trash restore rc", execute(token, cwd, home) == 0)
    check("trash content restored", target.exists() and digest(target) == before)


def case_trash_tree(tmp: Path) -> None:
    cwd, home = tmp / "p2", tmp / "h2"
    (cwd / "build").mkdir(parents=True); home.mkdir()
    files = {"a.js": "a", "b.js": "b"}
    for name, content in files.items():
        (cwd / "build" / name).write_text(content)
    c = card("rm -rf build", cwd, home)
    token = prepare(c["id"], cwd, home)
    shutil.rmtree(cwd / "build")
    check("tree restore rc", execute(token, cwd, home) == 0)
    for name, content in files.items():
        check(f"tree {name}", (cwd / "build" / name).read_text() == content)


def case_generated_artifact(tmp: Path) -> None:
    cwd, home = tmp / "p3", tmp / "h3"
    (cwd / "node_modules").mkdir(parents=True); home.mkdir()
    (cwd / "node_modules" / "dep.js").write_text("module.exports={};")
    c = card("rm -rf node_modules", cwd, home)
    check("artifact tier", c["tier"] == 1, str(c["tier"]))
    token = prepare(c["id"], cwd, home)
    shutil.rmtree(cwd / "node_modules")
    check("artifact restore rc", execute(token, cwd, home) == 0)
    check("artifact restored", (cwd / "node_modules" / "dep.js").exists())


def case_git_ref(tmp: Path) -> None:
    cwd, home = tmp / "p4", tmp / "h4"
    cwd.mkdir(); home.mkdir()
    git(["init", "-b", "main", "-q"], cwd)
    git(["config", "user.name", "Test"], cwd)
    git(["config", "user.email", "test@example.com"], cwd)
    (cwd / "app.js").write_text("original\n")
    git(["add", "-A"], cwd); git(["commit", "-qm", "init"], cwd)
    first = git(["rev-parse", "HEAD"], cwd)
    (cwd / "app.js").write_text("uncommitted work\n")
    c = card("git reset --hard HEAD~1", cwd, home)
    check("git strategy", c["strategy"] == "git-ref", c["strategy"])
    token = prepare(c["id"], cwd, home)
    git(["reset", "--hard"], cwd)
    check("git-ref restore rc", execute(token, cwd, home) == 0)
    check("git ref restored", git(["rev-parse", "HEAD"], cwd) == first)
    check("stash applied", (cwd / "app.js").read_text() == "uncommitted work\n")


def case_force_push(tmp: Path) -> None:
    cwd, home = tmp / "p5", tmp / "h5"
    cwd.mkdir(); home.mkdir()
    remote = tmp / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True)
    git(["init", "-b", "main", "-q"], cwd)
    git(["config", "user.name", "Test"], cwd)
    git(["config", "user.email", "test@example.com"], cwd)
    git(["checkout", "-qb", "feature"], cwd)
    (cwd / "f.txt").write_text("one\n")
    git(["add", "-A"], cwd); git(["commit", "-qm", "first"], cwd)
    original = git(["rev-parse", "HEAD"], cwd)
    git(["remote", "add", "origin", str(remote)], cwd)
    git(["push", "-q", "-u", "origin", "feature"], cwd)
    (cwd / "f.txt").write_text("two\n")
    git(["commit", "-qam", "second"], cwd)
    c = card("git push --force origin feature", cwd, home)
    check("force strategy", c["strategy"] == "force-push", c["strategy"])
    token = prepare(c["id"], cwd, home)
    git(["push", "--force", "origin", "feature"], cwd)
    check("force restore rc", execute(token, cwd, home) == 0)
    check("force remote restored",
          git(["ls-remote", "origin", "refs/heads/feature"], cwd).split()[0] == original)


def case_sqlite(tmp: Path) -> None:
    cwd, home = tmp / "p6", tmp / "h6"
    cwd.mkdir(); home.mkdir()
    db = cwd / "test.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    conn.executemany("INSERT INTO users VALUES (?,?)", [(1, "a"), (2, "b")])
    conn.commit(); conn.close()
    c = card("DROP TABLE users;", cwd, home)
    check("sql strategy", c["strategy"] == "sql-backup", c["strategy"])
    token = prepare(c["id"], cwd, home, ["--db", str(db)])
    conn = sqlite3.connect(db); conn.execute("DROP TABLE users"); conn.commit(); conn.close()
    check("sql restore rc", execute(token, cwd, home) == 0)
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    conn.close()
    check("sql rows restored", rows == 2, str(rows))


def case_t4(tmp: Path) -> None:
    cwd, home = tmp / "p7", tmp / "h7"
    cwd.mkdir(); home.mkdir()
    c = card("git push --force origin main", cwd, home)
    check("t4 tier", c["tier"] == 4, str(c["tier"]))
    result = call("undo.py", ["prepare", "--blast", c["id"]], cwd, home)
    check("t4 no token", result.returncode != 0 and "T4" in result.stderr, result.stderr)
    check("t4 no manifest", not list((home / "undos").glob("*.json")))


def case_drift(tmp: Path) -> None:
    cwd, home = tmp / "p8", tmp / "h8"
    cwd.mkdir(); home.mkdir()
    target = cwd / "data.txt"
    target.write_text("old\n")
    c = card("rm -rf data.txt", cwd, home)
    token = prepare(c["id"], cwd, home)
    target.write_text("new work\n")
    check("drift refused", execute(token, cwd, home) == 3)
    check("drift content intact", target.read_text() == "new work\n")


def case_receipts(tmp: Path) -> None:
    cwd, home = tmp / "p9", tmp / "h9"
    cwd.mkdir(); home.mkdir()
    target = cwd / "x.txt"; target.write_text("x")
    c = card("rm -rf x.txt", cwd, home)
    token = prepare(c["id"], cwd, home)
    target.unlink()
    check("receipt flow rc", execute(token, cwd, home) == 0)
    verify = call("receipt.py", ["verify"], cwd, home)
    check("chain valid", verify.returncode == 0, verify.stdout + verify.stderr)
    entries = [json.loads(line) for line in (home / "receipts.jsonl").read_text().splitlines()]
    check("prepared + undo receipts", len(entries) == 2, str(len(entries)))
    check("prepared recorded", entries[0]["type"] == "prepared"
          and entries[0]["undo_token"] == token)
    check("undo recorded", entries[-1]["type"] == "undo"
          and entries[-1]["undo_token"] == token)
    check("undo verified flag", entries[-1]["verified"] is True)
    added = call("receipt.py", ["add", "--command", "rm -rf x.txt", "--tier", "1",
                                "--undo-token", token, "--verified"], cwd, home)
    check("add receipt rc", added.returncode == 0, added.stderr)
    check("chain after add", call("receipt.py", ["verify"], cwd, home).returncode == 0)
    lines = (home / "receipts.jsonl").read_text().splitlines()
    broken = json.loads(lines[0]); broken["command"] = "tampered"
    (home / "receipts.jsonl").write_text(json.dumps(broken) + "\n")
    check("tamper detected", call("receipt.py", ["verify"], cwd, home).returncode == 1)


def case_prune_and_fresh_session(tmp: Path) -> None:
    cwd, home = tmp / "p10", tmp / "h10"
    cwd.mkdir(); home.mkdir()
    target = cwd / "old.txt"; target.write_text("old")
    c = card("rm -rf old.txt", cwd, home)
    token = prepare(c["id"], cwd, home)
    target.unlink()
    # Different process/cwd already; execute with a fresh subprocess.
    check("fresh session undo", call("undo.py", ["execute", token, "--approval", "yes"],
                                     cwd, home).returncode == 0)
    check("fresh session restore", target.read_text() == "old")
    manifest_path = home / "undos" / f"{token}.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["created"] = "2020-01-01T00:00:00+00:00"
    manifest_path.write_text(json.dumps(manifest))
    check("prune rc", call("undo.py", ["prune", "--older-than", "7"], cwd, home).returncode == 0)
    check("prune removed", not manifest_path.exists())


def main() -> int:
    cases = [
        case_trash_file, case_trash_tree, case_generated_artifact, case_git_ref,
        case_force_push, case_sqlite, case_t4, case_drift, case_receipts,
        case_prune_and_fresh_session,
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for case in cases:
            case(root)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} undo/receipt checks")
        for failure in FAILURES:
            print("  - " + failure)
        return 1
    print(f"PASS: all undo/receipt checks across {len(cases)} scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
