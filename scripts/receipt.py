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
import json
import os
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
    record["hash"] = entry_digest(record, prev_hash)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    return record


def verify() -> tuple[bool, list[str]]:
    entries = read_entries()
    problems = []
    prev_hash = "0" * 64
    for index, entry in enumerate(entries, start=1):
        if entry.get("seq") != index:
            problems.append(f"entry {index}: seq mismatch")
        if entry.get("prev_hash") != prev_hash:
            problems.append(f"entry {index}: broken hash chain")
        expected = entry_digest(entry, prev_hash)
        if entry.get("hash") != expected:
            problems.append(f"entry {index}: hash mismatch")
        prev_hash = entry.get("hash", "")
    return (not problems), problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "verify"], default="verify", nargs="?")
    args = parser.parse_args(argv)

    if args.action == "list":
        for entry in read_entries():
            print(
                f"#{entry['seq']} {entry.get('ts', '')} "
                f"{entry.get('type', 'action')} T{entry.get('tier', '?')} "
                f"{entry.get('command', '')} undo={entry.get('undo_token', '-')}"
            )
        return 0

    ok, problems = verify()
    if ok:
        print(f"PASS: {len(read_entries())} receipts, hash chain intact")
        return 0
    print("FAIL: receipt chain invalid")
    for problem in problems:
        print("  - " + problem)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
