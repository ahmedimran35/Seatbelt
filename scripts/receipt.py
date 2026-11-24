#!/usr/bin/env python3
"""Append-only, hash-chained Seatbelt receipts.

Each receipt contains the hash of the previous one, so editing or deleting an
entry breaks verification. This is tamper-evidence, not a digital signature.

Usage:
    python3 scripts/receipt.py list
    python3 scripts/receipt.py verify
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path(os.getenv("SEATBELT_HOME", str(Path.home() / ".seatbelt")))
LOG = HOME / "receipts.jsonl"


def receipt_log() -> Path:
    return Path(os.getenv("SEATBELT_RECEIPTS", str(LOG)))


def read_entries() -> list[dict[str, Any]]:
    path = receipt_log()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def key_path() -> Path:
    return HOME / "receipt.key"


def load_key(create: bool = True) -> bytes:
    path = key_path()
    if path.exists():
        return path.read_bytes()
    if not create:
        return b""
    path.parent.mkdir(parents=True, exist_ok=True)
    secret = os.urandom(32)
    path.write_bytes(secret)
    os.chmod(path, 0o600)
    return secret


def canonical(entry: dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"))


def command_digest(command: str) -> str:
    normalised = re.sub(r"\s+", " ", command).strip()
    return hashlib.sha256(normalised.encode()).hexdigest()


def sign(entry: dict[str, Any]) -> str:
    payload = {k: v for k, v in entry.items() if k not in ("sig", "hash")}
    return hmac.new(load_key(), canonical(payload).encode(), hashlib.sha256).hexdigest()


def has_prepared(command: str) -> bool:
    """True if an unconsumed prepared receipt exists for this exact command."""
    target = command_digest(command)
    seen_action = False
    for entry in read_entries():
        if entry.get("command_hash") != target:
            continue
        if entry.get("type") == "prepared" and not seen_action and entry.get("verified"):
            return True
        if entry.get("type") == "action":
            seen_action = True
    return False


def entry_digest(entry: dict[str, Any], prev_hash: str) -> str:
    payload = {key: value for key, value in entry.items() if key != "hash"}
    payload["prev_hash"] = prev_hash
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def append(entry: dict[str, Any]) -> dict[str, Any]:
    path = receipt_log()
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = read_entries()
    prev_hash = entries[-1].get("hash", "0" * 64) if entries else "0" * 64
    record = dict(entry)
    record["seq"] = len(entries) + 1
    record["ts"] = datetime.now(timezone.utc).isoformat()
    record["prev_hash"] = prev_hash
    if record.get("command"):
        record["command_hash"] = command_digest(record["command"])
    record["sig"] = sign(record)
    record["hash"] = entry_digest(record, prev_hash)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    return record


def verify() -> tuple[bool, list[str], int]:
    entries = read_entries()
    problems = []
    legacy = 0
    prev_hash = "0" * 64
    for index, entry in enumerate(entries, start=1):
        if entry.get("seq") != index:
            problems.append(f"entry {index}: seq mismatch")
        if entry.get("prev_hash") != prev_hash:
            problems.append(f"entry {index}: broken hash chain")
        expected = entry_digest(entry, prev_hash)
        if entry.get("hash") != expected:
            problems.append(f"entry {index}: hash mismatch")
        if "sig" in entry:
            if not hmac.compare_digest(entry["sig"], sign(entry)):
                problems.append(f"entry {index}: invalid HMAC signature")
        else:
            legacy += 1
        prev_hash = entry.get("hash", "")
    return (not problems), problems, legacy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "verify", "add", "check-command"],
                        default="verify", nargs="?")
    parser.add_argument("--command", default="")
    parser.add_argument("--tier", type=int, default=0)
    parser.add_argument("--undo-token", default="-")
    parser.add_argument("--approval", default="yes")
    parser.add_argument("--mode", default="full")
    parser.add_argument("--type", default="action")
    parser.add_argument("--notes", default="")
    parser.add_argument("--verified", action="store_true")
    args = parser.parse_args(argv)

    if args.action == "add":
        record = append({
            "type": args.type, "command": args.command, "tier": args.tier,
            "mode": args.mode, "approval": args.approval,
            "undo_token": args.undo_token, "verified": args.verified,
            "notes": args.notes, "agent_id": os.getenv("SEATBELT_AGENT_ID", "unknown"),
        })
        print(f"Receipt #{record['seq']} written")
        return 0

    if args.action == "check-command":
        if has_prepared(args.command):
            print(f"Prepared receipt found: {args.command}")
            return 0
        print(f"No unconsumed prepared receipt for: {args.command}")
        return 3

    if args.action == "list":
        for entry in read_entries():
            print(
                f"#{entry['seq']} {entry.get('ts', '')} "
                f"{entry.get('type', 'action')} T{entry.get('tier', '?')} "
                f"{entry.get('command', '')} undo={entry.get('undo_token', '-')}"
            )
        return 0

    ok, problems, legacy = verify()
    if ok:
        suffix = f", {legacy} legacy unsigned" if legacy else ""
        print(f"PASS: {len(read_entries())} receipts, hash chain and HMAC intact{suffix}")
        return 0
    print("FAIL: receipt chain invalid")
    for problem in problems:
        print("  - " + problem)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
