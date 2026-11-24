# Seatbelt

A portable, single-opinion agent skill: **before anything hard to undo, show the exact blast radius and get the right level of consent.** Some shapes are never allowed.

Like ponytail (write less code) or caveman (terse output), Seatbelt changes one behaviour rather than adding knowledge. It works by instruction in any agent, with an optional PreToolUse hook for deterministic enforcement in Claude Code.

## What it does

- Five tiers: T0 safe, T1 reversible, T2 risky, T3 catastrophic, **T4 never** (hard deny).
- Four levels: `lite`, `full` (default), `ultra`, `lockdown`.
- Environment bumps: production/shared, dirty tree, no backup, sandbox.
- Parses chains, pipes, `sudo`/`env`/`bash -c`/`eval`/`git -C` wrappers, substitutions, PowerShell/cmd aliases.
- Safe exceptions for generated artifacts and read-only previews.
- Real previews, rollback offers, typed `GO` for T3, grouped confirmations.
- **Undo + receipts** (the differentiator): every T1–T3 action gets a blast card from real state, an undo token, and an append-only, hash-chained, HMAC-authenticated receipt. `seatbelt undo <token>` restores the exact pre-state and refuses on drift. The hook denies commands with no prepared receipt.
- Optional Claude Code hook: deny/ask before every Bash/PowerShell/Edit/Write call, including `bypassPermissions` and subagents. JSONL decision log, protected file edits, merge-safe installer, idempotent uninstall.

## Quick start

```bash
# Portable skill
cp -R "/Users/imran/skills develop/seatbelt" ~/.agents/skills/seatbelt
cp -R "/Users/imran/skills develop/seatbelt" ~/.claude/skills/seatbelt

# Optional Claude Code enforcement
python3 ~/.claude/skills/seatbelt/scripts/install_hook.py install --scope project --mode full
python3 ~/.claude/skills/seatbelt/scripts/hook.py test

# Tests
python3 ~/.claude/skills/seatbelt/scripts/test_risk_check.py   # 85 checks
python3 ~/.claude/skills/seatbelt/scripts/test_hook.py        # 22 checks
python3 ~/.claude/skills/seatbelt/scripts/test_receipts.py    # undo + receipt checks

# Undo flow
python3 scripts/blast.py --command "rm -rf dist" --save --format text
python3 scripts/undo.py prepare --blast <card-id>
python3 scripts/undo.py execute <token> --approval yes
python3 scripts/receipt.py verify
```

SQL drops support SQLite, PostgreSQL and MySQL via `--adapter`. Secret-path backups require `--allow-secrets`; Terraform undo can store apply consent with `--apply-plan`.

Say `seatbelt lite`, `seatbelt full`, `seatbelt ultra`, or `seatbelt lockdown` to change levels. In OpenCode, use `@seatbelt` or `/seatbelt ultra`.

## Files

```
seatbelt/
├── SKILL.md                       # instruction core
├── scripts/
│   ├── risk_check.py              # classifier (JSON verdict + decision)
│   ├── blast.py                   # real-state blast card generator
│   ├── undo.py                    # prepare/check/execute/prune undo tokens
│   ├── receipt.py                 # append-only hash-chained receipts
│   ├── hook.py                    # PreToolUse hook + rules/test/check CLI
│   ├── install_hook.py            # merge-safe installer/uninstaller
│   ├── test_risk_check.py         # 85 checks
│   ├── test_hook.py               # 22 checks
│   └── test_receipts.py           # undo + receipt checks
├── assets/
│   ├── risk-patterns.json         # patterns + safe exceptions
│   └── undo-strategies.json       # prepare/verify/reverse templates
├── references/                    # risk model, catalog, rollback, hook setup,
│                                   # receipts, blast cards, known gaps, comparison
└── evals/                         # 20 prompts + undo cases + baseline log
```

## Honest limits

Seatbelt reads command text; it is not a sandbox, a policy boundary, or a replacement for branch protection, scoped credentials, and backups. See [references/known-gaps.md](references/known-gaps.md) and [references/comparison.md](references/comparison.md).

## License

MIT — see [LICENSE](LICENSE).
