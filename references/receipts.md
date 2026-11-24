# Undo tokens and receipts

This is the mechanism that distinguishes Seatbelt: consent produces a reversible token and an auditable receipt, not just a "yes".

## Contents
- State locations
- Token lifecycle
- Receipt format and hash chain
- What undo cannot do
- Commands

## State locations

All paths are under `SEATBELT_HOME` (default `~/.seatbelt`):

```
blasts/<id>.json       # blast cards
undos/<token>.json     # undo manifests
undos/<token>/...      # backups, mode 0700
receipts.jsonl         # append-only hash-chained + HMAC-authenticated receipts
receipt.key            # local 0600 HMAC key
decisions.jsonl        # hook decisions (separate)
```

Set `SEATBELT_HOME` to isolate a test run. Never store state inside the project being edited.

## Token lifecycle

1. **Prepare** — `python3 scripts/undo.py prepare --blast <id>` moves or copies the pre-state into `undos/<token>/` and writes a manifest with `expect` and `reverse` fields.
2. **Consent** — show the token with the blast card; do not execute without it.
3. **Execute** — the agent performs the action, verifies the post-state, then appends a receipt.
4. **Undo** — `check` verifies `expect`; `execute` reverses and appends a second receipt. Refuses if the destination was recreated with different content or the remote moved.
5. **Expiry** — manifests expire after 7 days; `prune --older-than 7d` removes them and their backups.

Tokens look like `20261124T220000Z-a1b2c3` (UTC timestamp + short hash of command and cwd).

## Receipt format and hash chain

```json
{"seq":42,"prev_hash":"...","hash":"...","ts":"...","type":"action",
 "command":"rm -rf dist","tier":1,"mode":"full","approval":"yes",
 "undo_token":"20261124T220000Z-a1b2c3","verified":true,"notes":"",
 "agent_id":"..."}
```

Each receipt stores the previous receipt's hash plus an HMAC over its contents, using `receipt.key` (mode 0600). `python3 scripts/receipt.py verify` recomputes both and reports breaks, edits, or invalid signatures. `command_hash` lets the hook check whether a `prepared` receipt exists for the exact command.

**This is tamper-evidence, not non-repudiation.** Someone who can read the local key can forge receipts; there is no trusted timestamp or external signing authority. Pre-1.2 receipts without `sig` are reported as legacy but still accepted by the chain check.

The Claude Code hook denies T1–T3 commands that lack an unconsumed `prepared` receipt. Disable deliberately with `"require_receipts": false` in `.seatbelt/mode.json`.

## What undo cannot do

- Restore credentials that were already read or exposed.
- Reverse changes made by other people to a remote after the backup.
- Resurrect processes killed with `kill -9`.
- Restore files modified after the blast card was generated — verification refuses.
- Restore T4 actions, because they are never executed.
- Restore data from a backup that was pruned after expiry.

Manifests containing secrets (`.env`, SSH keys, Terraform state) are marked `contains_secrets` and stored with mode `0700`. Backups of protected secret paths are not created by default; explicit user approval is required.

## Commands

```bash
python3 scripts/blast.py --command "rm -rf dist" --save --format text
python3 scripts/undo.py prepare --blast <id>
python3 scripts/undo.py check <token>
python3 scripts/undo.py execute <token> --approval yes
python3 scripts/undo.py list
python3 scripts/undo.py prune --older-than 7d
python3 scripts/receipt.py add --command "rm -rf dist" --tier 1 --undo-token <token> --verified
python3 scripts/receipt.py check-command --command "rm -rf dist"
python3 scripts/receipt.py list
python3 scripts/receipt.py verify
```

OpenCode aliases: `/seatbelt undo <token>`, `/seatbelt receipts`, `/seatbelt verify`.
