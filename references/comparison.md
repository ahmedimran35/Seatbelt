# Ecosystem comparison

Research date: 2026-11-24. Sources are public skills and hook projects. Star/install counts are directional only; the leaderboard has clone/namesquat inflation.

## What the strongest safety skills do

| Project | Core mechanism | Notable features |
|---|---|---|
| [garrytan/gstack — careful](https://github.com/garrytan/gstack/blob/main/careful/SKILL.md) | PreToolUse hook, `permissionDecision: ask` | PowerShell/cmd coverage, safe-artifact exceptions, HIGH tier hard deny for `/`, `~`, `$HOME` and default-branch force-push |
| [TracineHQ/guard](https://github.com/TracineHQ/guard/blob/HEAD/SKILL.md) | Deny-only hooks + decision log | `enforce/shadow/off/lockdown` modes, credential scanning, protected files, subagent scope, inline-interpreter and pipe-to-shell rules, admin-CLI default-deny, JSONL audit log |
| [milad-ahmd/agent-guardrails](https://milad-ahmd.github.io/agent-skills/skills/agent-guardrails/) | PreToolUse hook with deny/ask | `rules`, `test`, `check` CLI, ~60 samples, settings merge with backup + clean uninstall, parses wrappers/chains/heredocs, explicit known-gaps section |
| [mattpocock/skills — git-guardrails-claude-code](https://github.com/mattpocock/skills/blob/main/skills/misc/git-guardrails-claude-code/SKILL.md) | PreToolUse hook blocking git | Scope question (project vs global), copy hook + merge settings, mandatory interception test |
| [dyrits/skills — setup-git-guardrails](https://www.skills.sh/dyrits/skills/setup-git-guardrails) | Hook + git `pre-push` | Three guard levels (shared history / local work / strict), portable git layer |
| [pegasi-ai/reins](https://github.com/pegasi-ai/reins/blob/main/plugin/skills/reins/SKILL.md) | Pre/PostToolUse hooks | Block/warn/log tiers, MCP tool coverage, protected paths, cloud decision log |
| [karanb192/claude-code-hooks](https://pluginsmp.com/plugins/block-dangerous-commands) | PreToolUse hook | Three safety levels, per-level ask mode, every block logged with pattern id |
| [headroom](https://github.com/headroomlabs-ai/headroom) | Skill + proxy | Job-language description, short do-not list, intensity levels, plugin manifests for Claude/Codex/Copilot |

## What Seatbelt adopted

- **Deterministic enforcement** via PreToolUse hook, including bypass and subagent modes.
- **T4 hard deny** for the shapes careful and guard refuse outright.
- **Wrapper and chain parsing** (`sudo`, `env`, `bash -c`, `eval`, `git -C`, `$(...)`, backticks, pipes).
- **PowerShell/cmd patterns** and safe-artifact exceptions.
- **Modes** (`lite/full/ultra/lockdown`), persisted in a mode file or env var.
- **Audit log** in JSONL, decision reasons with preview and rollback.
- **Self-test CLI** (`rules`, `test`, `check`), idempotent installer with backup and uninstall.
- **Protected file edits** for `.env`, SSH keys, credentials, own config.
- **Honest known gaps** and a scanner note.
- **Job-language description** with trigger phrases for auto mode and guardrail requests.

## What Seatbelt deliberately does differently

- **Four risk tiers plus three conversation levels** instead of a binary deny/ask. The hook maps them to allow/ask/deny; the conversation adds typed `GO` and handoff.
- **Rollback-first**: every T2/T3 confirmation includes an undo option before consent.
- **Portable core**: the instruction skill works in agents with no hook support; the hook is a clearly marked Claude Code add-on.
- **Behaviour-shaped like ponytail/caveman**: one opinion, memorable name, levels, short `SKILL.md`, detail in references.

## What is still missing compared with the best

- No MCP tool coverage (reins).
- No admin-CLI default-deny for `aws`/`gcloud`/`az` (guard).
- No shadow mode that logs would-be denies without blocking (guard).
- No plugin marketplace manifests or `npx skills add` distribution yet.
- No separate git `pre-push` hook layer (dyrits).

These are tracked as optional future work; none is required for the core promise.
