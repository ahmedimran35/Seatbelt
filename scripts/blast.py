#!/usr/bin/env python3
"""Generate a blast card: an exact, real-state preview of a pending action.

Usage:
    python3 scripts/blast.py --command "rm -rf dist" --format text
    python3 scripts/blast.py --command "git reset --hard" --save --format json
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from risk_check import classify, load_config  # noqa: E402

HOME = Path(os.getenv("SEATBELT_HOME", str(Path.home() / ".seatbelt")))
WORDS = {
    "rm", "git", "push", "reset", "clean", "checkout", "restore", "switch",
    "branch", "delete", "drop", "table", "truncate", "find", "exec", "chmod",
    "chown", "kill", "dd", "mkfs", "docker", "kubectl", "helm", "terraform",
    "npm", "publish", "sudo", "env", "bash", "eval", "if", "exists", "from",
    "update", "set", "where", "and", "or", "true", "false", "main", "master",
    "origin", "hard", "force", "recursive",
}


def token_for(command: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(f"{Path.cwd()}\0{command}".encode()).hexdigest()[:6]
    return f"{stamp}-{digest}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def candidate_tokens(command: str) -> list[str]:
    raw = re.findall(r"[^\s\"'`|;&]+", command)
    out = []
    for item in raw:
        clean = item.strip("\"'")
        if not clean or clean.startswith("-") or "=" in clean:
            continue
        if clean.lower() in WORDS:
            continue
        out.append(clean)
    return out


def path_targets(command: str, cwd: Path) -> list[dict[str, Any]]:
    targets = []
    for token in candidate_tokens(command):
        expanded = glob.glob(token) if any(c in token for c in "*?[") else [token]
        for name in expanded[:50]:
            path = Path(name)
            if not path.is_absolute():
                path = cwd / path
            if not path.exists():
                continue
            relative = os.path.relpath(path, cwd)
            status = git("status", "--short", "--", relative)
            targets.append({
                "kind": "path",
                "path": str(path),
                "relative": relative,
                "size_bytes": path.stat().st_size if path.is_file() else None,
                "is_dir": path.is_dir(),
                "sha256": sha256_file(path) if path.is_file() else None,
                "git_status": status,
            })
    return targets


def git_targets(command: str) -> list[dict[str, Any]]:
    if not re.search(r"\bgit\b", command):
        return []
    targets = []
    for token in candidate_tokens(command):
        sha = git("rev-parse", "--verify", "--quiet", token)
        if not sha:
            continue
        ahead = git("log", "--oneline", f"origin/{token}..{token}")
        targets.append({
            "kind": "git-ref",
            "ref": token,
            "sha": sha,
            "remote_sha": git("rev-parse", "--verify", "--quiet", f"origin/{token}"),
            "ahead_commits": [line for line in ahead.splitlines() if line],
        })
    return targets


def load_strategies() -> dict[str, Any]:
    local = HERE / "assets" / "undo-strategies.json"
    path = local if local.exists() else HERE.parent / "assets" / "undo-strategies.json"
    return json.loads(path.read_text(encoding="utf-8"))


def choose_strategy(command: str, config: dict[str, Any]) -> str:
    for item in config.get("strategies", []):
        if re.search(item["regex"], command, re.IGNORECASE):
            return item["strategy"]
    return "none"


def preview_text(card: dict[str, Any]) -> str:
    lines = [
        f"Blast card {card['id']} | tier {card['tier']} | strategy {card['strategy']}",
        f"Command: {card['command']}",
    ]
    for target in card["targets"]:
        if target["kind"] == "path":
            size = target["size_bytes"]
            size_text = f"{size} bytes" if size is not None else "directory"
            lines.append(
                f"  path {target['relative']} — {size_text}"
                + (f" — sha256 {target['sha256'][:12]}" if target["sha256"] else "")
                + (f" — git: {target['git_status']}" if target["git_status"] else "")
            )
        else:
            lines.append(
                f"  ref {target['ref']} @ {target['sha'][:12]}"
                + (f", {len(target['ahead_commits'])} ahead of origin"
                   if target["ahead_commits"] else "")
            )
    if not card["targets"]:
        lines.append("  no statically resolvable targets — treat as unknown blast radius")
    for warning in card["warnings"]:
        lines.append("  WARNING: " + warning)
    lines.append(f"Undo token: {card['token']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True)
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument("--save", action="store_true", help="write the card under SEATBELT_HOME")
    args = parser.parse_args(argv)

    config = load_config()
    verdict = classify(args.command, config=config)
    strategies = load_strategies()
    cwd = Path.cwd()
    card = {
        "id": token_for(args.command),
        "token": token_for(args.command),
        "created": datetime.now(timezone.utc).isoformat(),
        "command": args.command,
        "cwd": str(cwd),
        "tier": verdict["tier"],
        "mode": verdict["mode"],
        "decision": verdict["decision"],
        "strategy": choose_strategy(args.command, strategies),
        "targets": path_targets(args.command, cwd) + git_targets(args.command),
        "warnings": list(verdict["reasons"]),
        "reversible_by": None,
    }
    card["reversible_by"] = card["strategy"] if card["strategy"] != "none" else None
    if not card["targets"]:
        card["warnings"].append("blast radius not fully resolved")
    card["token"] = card["id"]

    if args.save:
        directory = HOME / "blasts"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{card['id']}.json").write_text(
            json.dumps(card, indent=2) + "\n", encoding="utf-8"
        )

    if args.format == "json":
        print(json.dumps(card, indent=2))
    else:
        print(preview_text(card))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
