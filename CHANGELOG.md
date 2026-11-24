# Changelog

All notable changes to this skill.

## 1.2.0 — 2026-11-24

Fixed the five known limitations of v1.1.x:

- **Hook enforcement:** T1–T3 commands without an unconsumed `prepared` receipt are denied by the PreToolUse hook. Opt out with `"require_receipts": false` or `--no-receipt-enforcement`. `lite` stays warn-only.
- **Receipt authenticity:** HMAC over each receipt using a local 0600 key, in addition to the hash chain. `receipt.py verify` checks both; `check-command` lets the hook match commands by `command_hash`. Legacy unsigned receipts are reported, not rejected.
- **SQL adapters:** PostgreSQL (`psql`) and MySQL (`mysql`) join SQLite for backup/restore; adapter selected with `--adapter`.
- **Terraform consent:** `--apply-plan` at prepare time is stored in the undo token, so undo applies the saved plan automatically without a second manual step.
- **Secret paths:** backups of `.env`, SSH keys, credentials and Terraform state are refused unless `--allow-secrets` is passed explicitly; data is stored at mode `0700` and marked in the manifest.
- Updated `known-gaps.md`, `receipts.md`, `hook-setup.md`, `undo-strategies.json`; 13 undo scenarios and 14 hook decisions now covered.

## 1.1.0 — 2026-11-24

Added the uniqueness mechanism: **no T1–T3 action without a blast card, an undo token, and a receipt**.

- `scripts/blast.py` — real-state preview with exact paths, sizes, hashes, git refs and commit ranges; writes cards under `SEATBELT_HOME/blasts/`.
- `scripts/undo.py` — prepare/check/execute/list/prune. Strategies: `trash`, `git-ref`, `force-push`, `sql-backup` (SQLite), `terraform`. Refuses on state drift.
- `scripts/receipt.py` — append-only, hash-chained receipts; `verify` detects edits and broken chains. Tamper-evidence, not a signature.
- `assets/undo-strategies.json` — first-match strategy catalog with explicit limits.
- Hook reasons now state that an undo token must be prepared before execution.
- `SKILL.md` workflow updated: classify → blast card → prepare undo → consent → execute → verify → receipt → report → optional undo.
- New references: `receipts.md`, `blast-card.md`; updated `known-gaps.md`, README, portability, evals.

## 1.0.0 — 2026-11-24

First public release. An earlier local prototype had four risk tiers, three levels, and a 38-check classifier; its ideas were folded into this release before publication, so there is no separately published v1.

Core:
- Five risk tiers: T0 safe, T1 reversible, T2 risky, T3 catastrophic, T4 never (hard deny).
- Four levels: `lite`, `full` (default), `ultra`, `lockdown`.
- Environment bumps: production/shared, dirty tree, no backup, sandbox.
- Wrapper and chain parsing: assignments, `sudo`, `env`, `timeout`, `xargs`, `bash -c`, `eval`, `git -C`, `git -c`, `$(...)`, backticks, process substitution, PowerShell/cmd aliases.
- Safe exceptions for generated artifacts and read-only previews.
- Real previews, rollback offers, typed `GO` for T3, grouped confirmations.

Enforcement (optional Claude Code add-on):
- PreToolUse hook with allow/ask/deny, persisted modes, JSONL decision log, protected file edits.
- Merge-safe installer with backups, idempotent re-runs, and clean uninstall.
- `rules`, `test`, and `check` CLI for verification.

Documentation and tests:
- References for risk model, command catalog, rollback playbook, hook setup, known gaps, ecosystem comparison, portability.
- 85 classifier checks across 71 commands; 22 hook/installer checks; 20 eval prompts plus edge probes.
- Job-language description for automatic triggering in agent skill lists.

Designed after a survey of public safety skills and hook projects (gstack careful, TracineHQ guard, agent-guardrails, mattpocock git-guardrails, reins, block-dangerous-commands, headroom).
