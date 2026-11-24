# Risk model

## Contents
- Tier definitions
- Hard-deny tier
- Environment bumps
- Wrappers and chain parsing
- Safe exceptions
- Mode mapping
- Determining blast radius
- Worked examples
- Edge cases

## Tier definitions

A tier is a function of **reversibility × blast radius × environment**.

| Tier | Test | Typical targets |
|---|---|---|
| T0 Safe | Reversible by construction, or only your own scratch work | Reads, tests, `git status`, `git clean -nd`, `terraform plan`, edits to a file you created this session in a temp dir |
| T1 Reversible | Cheap, reliable undo exists | Generated artifacts (`node_modules`, `dist`, `build`, `__pycache__`), overwriting a tracked file with git history intact |
| T2 Risky | Undo costly or shared state affected | Force-push to a feature branch, `reset --hard`, `git clean -fd`, discarding local edits, branch deletion, mass delete of user files, `kubectl delete`, Docker prune, `sudo` |
| T3 Catastrophic | Data loss likely, undo impossible, or target unknown | `rm -rf` on broad paths, `DROP TABLE`, `TRUNCATE`, `DELETE`/`UPDATE` without `WHERE`, `terraform destroy`, `find -delete`, inline interpreter code, secret reads, `npm publish`, reflog expiry |
| T4 Never | Shape is denied regardless of level or user override in this skill | See below |

## Hard-deny tier

T4 exists because some commands are never reasonable for an agent to run, even when a user says "yes":

- `rm -rf /`, `~`, `$HOME`, `/*`
- Force-push to `main`/`master`, including `+refspec` syntax (`git push origin +main:main`)
- `dd` writing to `/dev/*`, `mkfs`, `Format-Volume`, `Clear-Disk`
- `curl … | sh`, `wget … | bash`, `iex`, `-EncodedCommand`
- Fork bombs (`:(){ :|:& };:`)
- PowerShell recursive delete at a drive root

The hook always denies T4; the skill always refuses it and offers a safe alternative. A user who genuinely needs one of these should run it themselves in a terminal they control.

## Environment bumps

Start from the base tier, then apply in order:

1. **Environment**: `production`, `shared`, `remote`, protected branch → `+1`; `sandbox` → `−1`; `local` → `0`.
2. **Dirty tree**: tier ≥ 1 with uncommitted user changes → `+1`.
3. **No backup**: tier ≥ 2 without a backup → `+1`.

Cap at T3, floor at T0. T4 is never bumped. Examples:

- `rm temp.log` clean local → T1; dirty tree → T2.
- `git push --force origin feature-x` → T2; production → T3; to `main` → T4.
- `rm -rf ./tmp` in a sandbox with throwaway data → T2.

## Wrappers and chain parsing

Before matching patterns, normalise the command:

- Split on `&&`, `||`, `;`, `|`, newlines; extract `$(...)`, backticks, `<(...)`.
- Strip leading `VAR=value`, `sudo`, `env`, `timeout`, `xargs`, `command`, `nice`, `nohup`.
- Unwrap `bash -c`, `sh -lc`, `eval` to inspect the inner command.
- Strip `git -C <path>` and `git -c <key=value>` so git patterns still fire.

The command's tier is the maximum across all segments and any whole-command patterns (pipe-to-shell, fork bombs). A harmless prefix cannot mask a destructive suffix: `git status && rm -rf ./data` is T3. Elevation and wrappers are recorded as reasons even after normalisation.

## Safe exceptions

Static patterns are broad by design. Two allowlists lower a tier, and the reason must appear in the preview:

| Pattern | Lowered to | Why |
|---|---|---|
| `rm -rf` of `node_modules`, `dist`, `build`, `.next`, `__pycache__`, `.cache`, `.turbo`, `coverage`, `.venv`, `vendor/bundle` | T1 | Generated and reproducible |
| `git push --dry-run`, `git clean -n`, `terraform plan`, `npm pack --dry-run` | T0 | Read-only preview |

A sandbox bump can additionally lower a narrow generated target to T0. Never lower T4, and never lower a user-created or ambiguous target.

## Mode mapping

| Mode | allow | ask | deny |
|---|---|---|---|
| `lite` | T0–T2 | T3 | T4 |
| `full` | T0 | T1–T3 | T4 |
| `ultra` | T0 | T1–T3 (hand off in conversation) | T4 |
| `lockdown` | T0 | none | T1–T4 |

In conversation, T3 requires a typed `GO` rather than "yes" at every level except `lockdown`, where nothing above T0 runs. The hook cannot collect a typed `GO`; it asks via Claude Code's permission prompt and logs the decision.

## Determining blast radius

Never guess. Run a read-only preview and quote its output:

| Action | Preview |
|---|---|
| Deleting files | `ls -la <paths>`, `du -sh <paths>`, `git status --short -- <paths>` |
| Git rewrite | `git log --oneline <remote>/<branch>..HEAD`, `git status --short` |
| SQL delete/update | `SELECT count(*) FROM <table> [WHERE ...]` |
| Schema drop | Row counts plus dependent object list |
| Cluster/infra | `kubectl get <resource> <name> -o yaml`, `terraform plan -destroy` |
| Credential paths | Confirm the file is not secret before reading |

Ambiguous target → T3 and stop.

## Worked examples

1. **Generated cleanup (T1, full):** show `du -sh node_modules dist`, note reproducibility, offer trash, one confirmation.
2. **Force-push to feature branch (T2, full):** show rewritten commits, create backup branch, suggest `--force-with-lease`, confirm.
3. **Force-push to main (T4, any level):** deny; offer a feature branch + PR.
4. **DROP COLUMN in production (T3, typed GO):** row count, dependent queries, backup, then `GO`.
5. **File you created this session (T0):** delete directly, no prompt.

## Edge cases

- **"Just do it."** Authorises the goal, not the bypass. Apply the level.
- **`--yes`, `--no-verify`, `sudo`.** Surface them; they are not consent.
- **Subagents and hooks.** The level applies to them; the Claude Code hook fires in subagents too.
- **Ordinary pushes.** `git push origin <feature-branch>` is routine work (T0/T1). Only force pushes, pushes to protected/default branches, and delete/mirror pushes are T2+. Do not nag on plain pushes.
- **Unknown pattern.** The classifier is a floor, not an oracle. Classify manually if a command looks risky.
- **Scripts and aliases.** The hook reads command text only. `npm run clean`, `./deploy.sh`, Makefiles, and git aliases can hide destructive work: [known-gaps.md](known-gaps.md).
