#!/usr/bin/env python3
"""Install or remove the Seatbelt PreToolUse hook without clobbering settings.

Usage:
    python3 scripts/install_hook.py install --scope project --mode full
    python3 scripts/install_hook.py install --scope user --dry-run
    python3 scripts/install_hook.py uninstall --scope project --remove-script
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCRIPT_MARKER = Path("seatbelt") / "hook.py"


def settings_path(scope: str, project_dir: Path) -> Path:
    if scope == "user":
        return Path.home() / ".claude" / "settings.json"
    if scope == "local":
        return project_dir / ".claude" / "settings.local.json"
    return project_dir / ".claude" / "settings.json"


def script_path(scope: str, project_dir: Path) -> Path:
    hooks_dir = Path.home() / ".claude" / "hooks" if scope == "user" \
        else project_dir / ".claude" / "hooks"
    return hooks_dir / SCRIPT_MARKER


def mode_path(scope: str, project_dir: Path) -> Path:
    if scope == "user":
        return Path.home() / ".seatbelt" / "mode.json"
    return project_dir / ".seatbelt" / "mode.json"


def load_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"seatbelt: {path} is not valid JSON; refusing to touch it ({exc})")
    if not isinstance(data, dict):
        raise SystemExit(f"seatbelt: {path} is not a JSON object; refusing to touch it")
    return data


def is_ours(handler: dict[str, Any], target: Path) -> bool:
    return str(target) in json.dumps(handler.get("args", []))


def write_settings(path: Path, settings: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(
            path.name + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S")
        )
        shutil.copy2(path, backup)
        print(f"Backup: {backup}")
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote: {path}")


def install(args: argparse.Namespace, project_dir: Path) -> int:
    settings_file = settings_path(args.scope, project_dir)
    target = script_path(args.scope, project_dir)
    mode_file = mode_path(args.scope, project_dir)
    settings = load_settings(settings_file)

    pre = settings.get("hooks", {}).get("PreToolUse", [])
    kept = []
    for group in pre:
        handlers = [h for h in group.get("hooks", []) if not is_ours(h, target)]
        if handlers:
            new_group = dict(group)
            new_group["hooks"] = handlers
            kept.append(new_group)

    kept.append({
        "matcher": "Bash|PowerShell|Edit|Write",
        "hooks": [{
            "type": "command",
            "command": "python3",
            "args": [str(target), "hook"],
            "timeout": 10,
        }],
    })
    settings.setdefault("hooks", {})["PreToolUse"] = kept

    if args.dry_run:
        print(json.dumps({
            "settings": str(settings_file),
            "script": str(target),
            "mode_file": str(mode_file),
            "mode": args.mode,
            "pretooluse_groups": len(kept),
        }, indent=2))
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        HERE, target.parent,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(HERE.parent / "assets", target.parent / "assets", dirs_exist_ok=True)
    print(f"Installed hook: {target}")
    write_settings(settings_file, settings)
    mode_file.parent.mkdir(parents=True, exist_ok=True)
    mode_file.write_text(json.dumps({"mode": args.mode}) + "\n", encoding="utf-8")
    print(f"Mode: {args.mode} ({mode_file})")
    print("Verify with /hooks, then: python3 " + str(target) + " test")
    return 0


def uninstall(args: argparse.Namespace, project_dir: Path) -> int:
    settings_file = settings_path(args.scope, project_dir)
    target = script_path(args.scope, project_dir)
    mode_file = mode_path(args.scope, project_dir)
    settings = load_settings(settings_file)

    pre = settings.get("hooks", {}).get("PreToolUse", [])
    kept = []
    removed = 0
    for group in pre:
        handlers = [h for h in group.get("hooks", []) if not is_ours(h, target)]
        removed += len(group.get("hooks", [])) - len(handlers)
        if handlers:
            new_group = dict(group)
            new_group["hooks"] = handlers
            kept.append(new_group)
    settings.setdefault("hooks", {})["PreToolUse"] = kept

    if args.dry_run:
        print(json.dumps({"settings": str(settings_file), "entries_removed": removed}, indent=2))
        return 0
    if not removed:
        print("No Seatbelt hook entry found; nothing removed.")
        return 0

    write_settings(settings_file, settings)
    if args.remove_script and target.parent.exists():
        shutil.rmtree(target.parent)
        print(f"Removed hook directory: {target.parent}")
    if args.remove_mode and mode_file.exists():
        mode_file.unlink()
        print(f"Removed mode file: {mode_file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument("--scope", default="project", choices=["project", "local", "user"])
    parser.add_argument("--project-dir", default=".", help="project root (for testing)")
    parser.add_argument("--mode", default="full", choices=["lite", "full", "ultra", "lockdown"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove-script", action="store_true")
    parser.add_argument("--remove-mode", action="store_true")
    args = parser.parse_args(argv)
    project_dir = Path(args.project_dir).expanduser().resolve()

    if args.action == "install":
        return install(args, project_dir)
    return uninstall(args, project_dir)


if __name__ == "__main__":
    raise SystemExit(main())
