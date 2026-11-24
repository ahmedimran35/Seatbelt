---
name: seatbelt
description: Stops before irreversible actions — classifies risk by reversibility, blast radius, and environment, then previews exact targets, offers a rollback, and confirms or denies. Use before cleanup, rm -rf, force-push, hard reset, mass deletes, schema drops, infra teardown, or when the user asks for a cautious workflow, git safety hooks, to stop an agent from pushing, protect main, add a PreToolUse hook, or work in auto/bypass-permission mode. Levels: lite, full, ultra, lockdown.
license: MIT
metadata:
  version: "1.2"
---

# Seatbelt

Before any irreversible action, know exactly what will be affected and get the right level of consent. This covers shell commands, tool calls, edits that overwrite existing work, and actions taken by subagents you dispatch. Behaviour comes first; an optional hook adds deterministic enforcement where the agent supports it.

## Levels

The user can say "seatbelt lite", "seatbelt full", "seatbelt ultra", or "seatbelt lockdown". Default is `full`. Note the level once when it changes.

| Level | T0 | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|
| `lite` | Run | Run + short note | Warn, then run | Ask / typed `GO` | Deny |
| `full` | Run | Preview + confirm | Preview + confirm + rollback | Typed `GO` + backup | Deny |
| `ultra` | Run | Hand off command | Hand off command | Hand off command | Deny |
| `lockdown` | Run | Deny | Deny | Deny | Deny |

T4 is a hard deny at every level. T3 always requires a typed `GO` in conversation, even at `lite`. `ultra` executes nothing above T0. `lockdown` is for unattended or driven sessions.

## Risk tiers

| Tier | Meaning | Examples |
|---|---|---|
| T0 Safe | Reversible by construction, or scoped to your own scratch work | Reads, tests, `git status/diff/log`, `git clean -nd`, `terraform plan`, edits to a file you created this session in a temp dir |
| T1 Reversible | A cheap, reliable undo exists | Generated artifacts (`node_modules`, `dist`, `build`, `__pycache__`), overwriting a tracked file with git history intact |
| T2 Risky | Undo is costly or affects shared state | Force-push to a feature branch, `reset --hard`, `git clean -fd`, mass delete of user files, `kubectl delete`, `docker system prune`, `sudo` |
| T3 Catastrophic | Data loss likely, undo may be impossible, or target unknown | `rm -rf` on broad paths, `DROP TABLE`, `TRUNCATE TABLE`, `DELETE`/`UPDATE` without `WHERE`, `terraform destroy`, `find -delete`, inline interpreter code, credential reads, `npm publish` |
| T4 Never | Hard deny, no override in this skill | `rm -rf /`, `~`, `$HOME`, `/*`; force-push to `main`/`master`; `+refspec` force-push to default branch; `dd of=/dev/*`; `mkfs`; `curl … \| sh`; fork bombs; PowerShell `-EncodedCommand` / `iex` |

**Environment bumps:** production, shared/protected branch, uncommitted user work, or no backup → tier +1 (capped at T3). Sandbox temp dir, throwaway test DB, or a file you created this session → tier −1 (floor T0). Unknown blast radius → T3 and stop. T4 is never bumped down.

Full logic: [references/risk-model.md](references/risk-model.md). Tool catalog: [references/command-catalog.md](references/command-catalog.md). Undo options: [references/rollback-playbook.md](references/rollback-playbook.md).

## Procedure

1. **Classify before you act.** Check every segment of `&&`, `||`, `;`, `|`, newlines, `$(...)`, backticks, and `<(...)`. Strip leading `VAR=value`, `sudo`, `env`, `timeout`, `xargs`, `bash -c`, `eval`, `git -C` and `git -c` wrappers first — a safe prefix cannot smuggle a destructive suffix.
2. **Use the classifier when available.** Run `python3 scripts/risk_check.py --command "<command>"` from this folder; pass `--env`, `--tree`, `--backup`, `--target-known`, and `--mode` when known. If Python is unavailable, classify by hand with the tables above.
3. **Apply environment bumps**, then choose the behaviour from the Levels table.
4. **Generate a blast card from real state.** Run `python3 scripts/blast.py --command "<command>" --save --format text`. It lists exact paths with sizes and hashes, git refs with commit ranges, and the chosen undo strategy. If targets cannot be resolved, treat the action as T3 and stop. See [references/blast-card.md](references/blast-card.md).
5. **Prepare an undo token before asking.** Run `python3 scripts/undo.py prepare --blast <card-id>` (add `--db` for SQLite drops or `--terraform-plan` for Terraform). The token is printed and a manifest is stored. T4 gets no token — it is denied outright.
6. **Show the blast card, the undo token, and the rollback** in one request. Yes/no for T1–T2; typed `GO` for T3. Do not treat `--yes`, `--no-verify`, `sudo`, a subagent, a hook, or "just do it" as consent. Undo options: [references/rollback-playbook.md](references/rollback-playbook.md).
7. **Batch grouped requests** into one blast card and one confirmation.
8. **Execute only after consent.** No token means no execution for T1–T3.
9. **Verify the post-state** against the manifest, then record the executed action: `python3 scripts/receipt.py add --command "<command>" --tier <n> --undo-token <token> --verified`. `python3 scripts/receipt.py verify` checks the chain. Preparation already wrote a `prepared` receipt. Receipts are append-only and hash-chained, not cryptographically signed: [references/receipts.md](references/receipts.md).
10. **Report** the undo token, receipt number, and a short blast log: what changed, what was removed, nothing else.
11. **On request, undo:** `python3 scripts/undo.py check <token>` then `python3 scripts/undo.py execute <token> --approval yes`. Undo is T2 — confirm first, and it refuses if state drifted.

## Safe exceptions

Static patterns are deliberately conservative. These are lowered automatically and must be stated in the preview:

- `rm -rf` of `node_modules`, `dist`, `build`, `.next`, `__pycache__`, `.cache`, `.turbo`, `coverage`, `.venv` → T1 (generated, reproducible).
- `git push --dry-run`, `git clean -n`, `terraform plan`, `npm pack --dry-run` → T0.

Never lower a tier for a user-created or ambiguous target. Never lower T4.

## Optional deterministic enforcement

The portable core is instruction-only. For Claude Code, an optional PreToolUse hook enforces the same rules before every `Bash`, `PowerShell`, `Edit`, and `Write` call, including in `bypassPermissions` mode and inside subagents:

```bash
python3 scripts/install_hook.py install --scope project --mode full
python3 scripts/hook.py test
```

The installer backs up `settings.json`, merges one hook group, never overwrites other hooks, and supports `uninstall`. The hook writes decisions to `~/.seatbelt/decisions.jsonl`; mode can be set in `.seatbelt/mode.json` or with `SEATBELT_MODE`. It also blocks edits to `.env`, SSH keys, cloud credentials, and its own mode file. It is a guard for an honest agent, **not a security boundary**: [references/hook-setup.md](references/hook-setup.md), [references/known-gaps.md](references/known-gaps.md).

## Do NOT

- Do not flag reads, tests, or harmless T0 edits — no nagging.
- Do not ask twice about the same confirmed action.
- Do not treat "clean this up" as permission to remove files you did not create — list them first.
- Do not bypass confirmation through subagents, hooks, `sudo`, `--yes`, or chained commands.
- Do not proceed when the blast radius is unknown.
- Do not describe a dry-run as a real run, or silently lower the level.
- Do not claim the hook is a sandbox or a hard security boundary.

## Examples

**Force-push at `full`:**
> "Force-push rewrites `origin/feature-x`. Preview: 3 remote commits replaced. Rollback: I'll create `backup/pre-force-push` first. Proceed? [yes/no]"

**Hard deny at any level:**
> "Blocked: force-push to `main` is T4. I can push to a feature branch and open a PR instead."

**At `ultra`:**
> "Run this yourself: `git push --force-with-lease origin feature-x`"

## Install and portability

Core files are portable across Claude Code, OpenCode, Codex, Cursor, and Copilot. The hook is a Claude Code add-on. See [references/portability.md](references/portability.md).
