# Blast cards

A blast card is a machine-readable preview generated from **real state**, not from the command text alone. It is the input to undo preparation.

## Schema

```json
{
  "id": "20261124T220000Z-a1b2c3",
  "token": "20261124T220000Z-a1b2c3",
  "created": "2026-11-24T22:00:00+00:00",
  "command": "rm -rf dist",
  "cwd": "/path/to/project",
  "tier": 1,
  "mode": "full",
  "decision": "ask",
  "strategy": "trash",
  "targets": [
    {"kind": "path", "path": "/abs/dist/app.js", "relative": "dist/app.js",
     "size_bytes": 6, "is_dir": false, "sha256": "...", "git_status": ""}
  ],
  "warnings": ["file deletion"],
  "reversible_by": "trash"
}
```

Git targets use `kind: "git-ref"` with `ref`, `sha`, `remote_sha`, and `ahead_commits`.

## Human view

```
Blast card 20261124T220000Z-a1b2c3 | tier 1 | strategy trash
Command: rm -rf dist
  path dist/app.js — 6 bytes — sha256 601ecde1a3f1 — git:
Undo token: 20261124T220000Z-a1b2c3
```

## Strategy selection

The first matching regex in `assets/undo-strategies.json` wins:

| Command shape | Strategy |
|---|---|
| `DROP TABLE` / `TRUNCATE TABLE` | `sql-backup` (needs `--db`) |
| `terraform destroy` | `terraform` (state backup, optional plan) |
| `git push --force` / `-f` | `force-push` (backup tag at remote SHA) |
| `git reset --hard`, rebase, stash drop | `git-ref` (ref + stash) |
| `rm` / `Remove-Item` | `trash` (manifested move) |
| unmatched | `none` — no undo, so no execution for T1–T3 |

## Rules

- If no targets resolve, add the warning `blast radius not fully resolved` and treat as T3.
- Never show a guessed target. Quote the card's real paths, sizes, hashes, and commit ranges.
- Show the token before asking for consent.
- Do not prepare an undo before you have decided to ask — preparation changes the filesystem.
- Keep cards outside the project (`SEATBELT_HOME/blasts/`).
