# Changelog

All notable changes to this skill.

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
