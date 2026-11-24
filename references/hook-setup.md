# Hook setup (Claude Code add-on)

The portable skill works by instruction. This optional layer enforces the same rules before every tool call, including in `bypassPermissions` mode, auto mode, and subagents.

## Install

```bash
python3 scripts/install_hook.py install --scope project --mode full   # .claude/settings.json (shared with team)
python3 scripts/install_hook.py install --scope local  --mode full   # .claude/settings.local.json (just you)
python3 scripts/install_hook.py install --scope user  --mode full   # ~/.claude/settings.json (all projects)
python3 scripts/install_hook.py install --scope project --dry-run    # show plan, write nothing
python3 scripts/hook.py test                                        # 12 decision checks
```

The installer:
- copies the scripts and assets to `.claude/hooks/seatbelt/` (or `~/.claude/hooks/seatbelt/`), so `hook.py` can import `risk_check.py` and load `assets/risk-patterns.json`;
- adds one `PreToolUse` group with matcher `Bash|PowerShell|Edit|Write`;
- merges into existing `hooks.PreToolUse` without removing other entries;
- backs up the old settings file as `settings.json.bak-<timestamp>`;
- writes `{"mode": "..."}` to `.seatbelt/mode.json` (or `~/.seatbelt/mode.json`);
- is idempotent: re-running with the same scope does not duplicate the hook;
- refuses to touch a settings file that is not valid JSON.

Remove with `python3 scripts/install_hook.py uninstall --scope project --remove-script --remove-mode`. Always tell the user which scope you are installing to — `user` affects every project.

Verify with `/hooks`, then try a harmless blocked command such as `python3 scripts/hook.py check "git push --force origin main"` (exit 4 = deny, 3 = ask, 0 = allow).

## What the hook emits

Safe calls: no output, exit 0 — normal permission flow continues. The hook never auto-approves.

Dangerous calls: structured JSON on stdout, exit 0:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "Seatbelt T2 Risky (full mode) — ASK | Why: ... | Preview: ... | Rollback: ..."
  }
}
```

`deny` is used for T4 and protected paths. The reason names the rule, the preview, and the rollback so the agent picks a safe alternative instead of retrying.

## Modes

Set one of:

- `.seatbelt/mode.json` → `{"mode": "ultra"}`
- `~/.seatbelt/mode.json` → fallback for all projects
- `SEATBELT_MODE=lite` environment variable → highest priority

The slash command `/seatbelt lite` writes the project mode file and the hook picks it up on the next tool call.

## Receipt enforcement

By default the hook denies T1–T3 commands that have no unconsumed `prepared` receipt matching the command hash. The intended flow is:

```bash
python3 scripts/blast.py --command "rm -rf dist" --save
python3 scripts/undo.py prepare --blast <card-id>   # writes a prepared receipt
# now the hook allows the command to reach the permission prompt
```

After execution, record the action with `python3 scripts/receipt.py add ... --verified`. Undo writes a second receipt. `lite` mode disables this check. To keep the old warn-only behaviour, install with `--no-receipt-enforcement` or set `"require_receipts": false` in `.seatbelt/mode.json`.

## Audit log

Every decision is appended as one JSON line to `~/.seatbelt/decisions.jsonl` (override with `SEATBELT_LOG`):

```json
{"ts":"2026-11-24T...","command":"git push --force origin main","tier":2,"decision":"ask","mode":"full","reasons":["rewrites remote history"]}
```

The log records decisions, not a security guarantee. Do not put secrets in commands you want logged.

## Protected file edits

`Edit`, `Write`, and `MultiEdit` are denied for:

- `.env` and `.env.*`
- `~/.ssh/*`, `id_rsa`, `id_ed25519`
- cloud credential paths (`aws/credentials`, `gcloud`, `kube`)
- `/etc/shadow`
- `.seatbelt/mode.json` (the hook's own configuration)

Claude Code's `Read` tool is not covered. Add deny rules in the same settings file if needed:

```json
"permissions": { "deny": ["Read(./.env)", "Read(./.env.*)"] }
```

Note this also blocks `.env.example`; add an allow rule if you need it.

## Other agents

The hook's `check` and `rules` commands are portable. For Cursor/Codex, wire `python3 scripts/hook.py hook` into their command-hook event if supported; for agents with no hooks, print the rules with `python3 scripts/hook.py rules --text` into `AGENTS.md` or `.cursorrules` and say plainly that it is advice the model can ignore.
