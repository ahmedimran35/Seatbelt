# Changelog

All notable changes to this skill.

## 2.0.0 — 2026-11-24

Major upgrade after a survey of public safety skills and hook projects (gstack careful, TracineHQ guard, agent-guardrails, mattpocock git-guardrails, reins, block-dangerous-commands, headroom).

- Added T4 "Never" hard-deny tier: root/home deletes, default-branch force-push, `dd of=/dev`, `mkfs`, pipe-to-shell, fork bombs, PowerShell encoded commands.
- Added deterministic PreToolUse hook with allow/ask/deny, persisted modes, JSONL audit log, protected file edits, and a merge-safe installer/uninstaller with backups.
- Added `lockdown` mode and mode resolution via `.seatbelt/mode.json`, `~/.seatbelt/mode.json`, or `SEATBELT_MODE`.
- Added wrapper and chain parsing: assignments, `sudo`, `env`, `timeout`, `xargs`, `bash -c`, `eval`, `git -C`, `git -c`, `$(...)`, backticks, process substitution, PowerShell/cmd aliases.
- Added safe-artifact and dry-run exceptions.
- Added rules/test/check CLI, 85 classifier checks, 22 hook/installer checks, 20 eval prompts.
- Added references: hook setup, known gaps, ecosystem comparison.
- Expanded job-language description for auto-mode trigger phrases.

## 1.0.0 — 2026-11-24

- First release: four risk tiers, three levels, progressive-disclosure references, 38-check classifier, 12-case eval suite, portable install.
