#!/usr/bin/env python3
"""Seatbelt risk classifier (v2).

Reads assets/risk-patterns.json, normalises shell wrappers and chains, classifies
each segment, applies environment bumps, and returns a mode-aware decision.
Stdlib only.

Usage:
    python3 scripts/risk_check.py --command "git push --force origin feature-x"
    python3 scripts/risk_check.py --command "rm -rf /" --mode full --format text
    python3 scripts/risk_check.py --command "npm test" --log ~/.seatbelt/decisions.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_PATH = SKILL_ROOT / "assets" / "risk-patterns.json"
TIER_NAMES = {
    0: "T0 Safe", 1: "T1 Reversible", 2: "T2 Risky",
    3: "T3 Catastrophic", 4: "T4 Never",
}

NON_TARGET_WORDS = {
    "git", "push", "reset", "clean", "checkout", "restore", "switch", "branch",
    "delete", "kubectl", "helm", "docker", "system", "prune", "terraform",
    "destroy", "chmod", "chown", "kill", "mkfs", "dd", "truncate", "rm",
    "sudo", "from", "table", "update", "into", "database", "schema", "drop",
    "where", "set", "find", "exec", "publish", "stash", "reflog", "gc",
}

WRAPPER_RE = re.compile(
    r"^(?:sudo|runas|env(?:\s+[A-Za-z_][A-Za-z0-9_]*=[^\s]+)*|"
    r"timeout\s+\S+|xargs|command|nice|nohup)\s+",
    re.IGNORECASE,
)
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=[^\s]+\s+")
QUOTED_RE = re.compile(r'^(?:"([^"]*)"|\'([^\']*)\'|(\S+))')


def split_segments(command: str) -> list[str]:
    """Split chains, newlines, and pull out substitution bodies."""
    text = command.replace("\n", " ; ")
    parts = [p.strip() for p in re.split(r"&&|\|\||[;|]", text) if p.strip()]
    for inner in re.findall(r"\$\(([^)]*)\)|`([^`]*)`|<\(([^)]*)\)", text):
        body = next((p for p in inner if p), "").strip()
        if body:
            parts.append(body)
    return parts or [command.strip()]


def unquote(text: str) -> str:
    match = QUOTED_RE.match(text.strip())
    if not match:
        return text.strip()
    return next((group for group in match.groups() if group is not None), text.strip())


def normalise_segment(segment: str) -> str:
    """Strip wrappers and assignments so patterns see the real command."""
    text = segment.strip()
    for _ in range(8):
        changed = False
        new = ASSIGN_RE.sub("", text)
        if new != text:
            text, changed = new, True
        new = WRAPPER_RE.sub("", text)
        if new != text:
            text, changed = new, True
        if not changed:
            break

    shell = re.match(
        r"^(?:bash|sh|zsh|dash|powershell|pwsh)\s+-[a-zA-Z]*c\s+(.*)$",
        text, re.IGNORECASE,
    )
    if shell:
        text = unquote(shell.group(1))
    evaluator = re.match(r"^eval\s+(.+)$", text, re.IGNORECASE)
    if evaluator:
        text = unquote(evaluator.group(1))

    text = re.sub(r"^git\s+(?:-C\s+\S+\s+|-c\s+\S+\s+)+", "git ", text,
                  flags=re.IGNORECASE)
    return text.strip()


def guess_target(segment: str) -> str:
    for token in segment.split():
        clean = token.strip("\"'")
        if not clean or clean.startswith("-") or clean.lower() in NON_TARGET_WORDS:
            continue
        return clean
    return "<target>"


def decide(tier: int, mode: str) -> str:
    """Map a tier plus a user-selected mode to a hook decision."""
    if tier >= 4:
        return "deny"
    if mode == "lite":
        return "ask" if tier >= 3 else "allow"
    if mode == "full":
        return "ask" if tier >= 1 else "allow"
    if mode == "ultra":
        return "ask" if tier >= 1 else "allow"
    if mode == "lockdown":
        return "allow" if tier == 0 else "deny"
    return "ask" if tier >= 2 else "allow"


def classify(command: str, *, env: str = "local", tree: str = "clean",
             backup: str = "yes", target_known: str = "yes",
             mode: str = "full", config: dict[str, Any]) -> dict[str, Any]:
    defaults = config["defaults"]
    patterns = config["patterns"]
    exceptions = config.get("safe_exceptions", [])
    never_tier = int(defaults.get("never_tier", 4))
    bump_cap = int(defaults.get("max_bump_tier", 3))

    segment_reports: list[dict[str, Any]] = []
    whole_reports: list[dict[str, Any]] = []
    reasons: list[str] = []
    previews: list[str] = []
    rollbacks: list[str] = []

    for pattern in patterns:
        if pattern.get("scope") != "command":
            continue
        if re.search(pattern["regex"], command, re.IGNORECASE):
            whole_reports.append({
                "command": command,
                "scope": "command",
                "normalised": None,
                "tier": int(pattern["tier"]),
                "tier_name": TIER_NAMES.get(int(pattern["tier"]), ""),
                "matched_patterns": [pattern["id"]],
                "reasons": list(pattern["reasons"]),
                "preview": pattern["preview"],
                "rollback": pattern["rollback"],
            })

    for original in split_segments(command):
        segment = normalise_segment(original)
        seg_tier = int(defaults["safe_tier"])
        seg_reasons: list[str] = []
        seg_preview = ""
        seg_rollback = ""
        matched: list[str] = []

        for pattern in patterns:
            if not re.search(pattern["regex"], segment, re.IGNORECASE):
                continue
            matched.append(pattern["id"])
            seg_tier = max(seg_tier, int(pattern["tier"]))
            seg_reasons.extend(pattern["reasons"])
            if not seg_preview:
                target = guess_target(segment)
                seg_preview = pattern["preview"].replace("<target>", target)
            if not seg_rollback:
                seg_rollback = pattern["rollback"]

        if re.search(r"\b(?:sudo|runas)\b", original, re.IGNORECASE):
            seg_tier = max(seg_tier, 2)
            seg_reasons.append("elevated privileges")
        if re.search(r"\b(?:bash|sh|zsh|powershell|pwsh)\s+-[a-zA-Z]*c\b|\beval\b",
                     original, re.IGNORECASE):
            seg_reasons.append("shell/eval wrapper: inner command inspected")

        for exception in exceptions:
            if seg_tier >= 4 or not re.search(exception["regex"], segment, re.IGNORECASE):
                continue
            seg_tier = min(seg_tier, int(exception["max_tier"]))
            seg_reasons.append(f"{exception['id']}: {exception['reason']}")
            matched.append("exception:" + exception["id"])

        if target_known == "no":
            seg_tier = max(seg_tier, int(defaults["unknown_target_tier"]))
            seg_reasons.append("blast radius unknown")

        segment_reports.append({
            "command": original,
            "normalised": segment if segment != original else None,
            "tier": seg_tier,
            "tier_name": TIER_NAMES.get(seg_tier, f"T{seg_tier}"),
            "matched_patterns": matched,
            "reasons": sorted(set(seg_reasons)),
            "preview": seg_preview,
            "rollback": seg_rollback,
        })
        reasons.extend(seg_reasons)
        if seg_preview:
            previews.append(seg_preview)
        if seg_rollback:
            rollbacks.append(seg_rollback)

    for report in whole_reports:
        reasons.extend(report["reasons"])
        if report["preview"]:
            previews.append(report["preview"])
        if report["rollback"]:
            rollbacks.append(report["rollback"])

    all_reports = segment_reports + whole_reports
    tier = max((s["tier"] for s in all_reports), default=0)
    bumps: list[str] = []

    if tier < never_tier:
        env_delta = int(defaults["bumps"]["env"].get(env.lower(), 0))
        if env_delta:
            tier = min(max(tier + env_delta, 0), bump_cap)
            bumps.append(f"{env}: {env_delta:+d}")

        if tree == "dirty" and tier >= int(defaults["bumps"]["dirty_tree_min_tier"]):
            if tier < bump_cap:
                tier += 1
            bumps.append("dirty tree: +1")

        if backup == "no" and tier >= int(defaults["bumps"]["no_backup_min_tier"]):
            if tier < bump_cap:
                tier += 1
            bumps.append("no backup: +1")

    tier = min(max(tier, 0), never_tier)
    decision = decide(tier, mode)

    return {
        "command": command,
        "tier": tier,
        "tier_name": TIER_NAMES.get(tier, f"T{tier}"),
        "mode": mode,
        "decision": decision,
        "environment": {"env": env, "tree": tree, "backup": backup,
                        "target_known": target_known},
        "bumps": bumps,
        "typed_go_required": tier >= 3,
        "backup_required": tier >= 3 and backup == "no",
        "never_tier": tier >= never_tier,
        "segments": all_reports,
        "reasons": sorted(set(reasons)),
        "previews": previews,
        "rollbacks": sorted(set(rollbacks)),
    }


def format_text(verdict: dict[str, Any]) -> str:
    lines = [
        f"{verdict['tier_name']} (tier {verdict['tier']}) — decision: {verdict['decision'].upper()}",
        f"Environment: {verdict['environment']}",
    ]
    if verdict["bumps"]:
        lines.append("Bumps: " + ", ".join(verdict["bumps"]))
    for seg in verdict["segments"]:
        lines.append(f"  [{seg['tier_name']}] {seg['command']}")
        if seg["normalised"]:
            lines.append(f"    normalised: {seg['normalised']}")
        if seg["matched_patterns"]:
            lines.append("    matched: " + ", ".join(seg["matched_patterns"]))
        for reason in seg["reasons"]:
            lines.append(f"    - {reason}")
        if seg["preview"]:
            lines.append(f"    preview: {seg['preview']}")
        if seg["rollback"]:
            lines.append(f"    rollback: {seg['rollback']}")
    if verdict["never_tier"]:
        lines.append("Hard deny at every mode — never execute.")
    elif verdict["typed_go_required"]:
        lines.append("Typed GO required at every level.")
    if verdict["backup_required"]:
        lines.append("Backup required before proceeding.")
    return "\n".join(lines)


def load_config() -> dict[str, Any]:
    return json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))


def append_log(path: str, verdict: dict[str, Any]) -> None:
    log_path = Path(path).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "command": verdict["command"],
        "tier": verdict["tier"],
        "decision": verdict["decision"],
        "mode": verdict["mode"],
        "reasons": verdict["reasons"],
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True, help="command string to classify")
    parser.add_argument("--env", default="local",
                        help="environment: local, sandbox, shared, or production")
    parser.add_argument("--tree", default="clean", choices=["clean", "dirty"])
    parser.add_argument("--backup", default="yes", choices=["yes", "no"])
    parser.add_argument("--target-known", default="yes", choices=["yes", "no"])
    parser.add_argument("--mode", default="full",
                        choices=["lite", "full", "ultra", "lockdown"])
    parser.add_argument("--format", default="json", choices=["json", "text"])
    parser.add_argument("--log", help="append a JSONL decision to this file")
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"seatbelt: cannot load patterns: {exc}", file=sys.stderr)
        return 2

    verdict = classify(
        args.command,
        env=args.env,
        tree=args.tree,
        backup=args.backup,
        target_known=args.target_known,
        mode=args.mode,
        config=config,
    )
    if args.log:
        append_log(args.log, verdict)
    if args.format == "text":
        print(format_text(verdict))
    else:
        print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
