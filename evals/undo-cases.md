# Undo eval cases

Automated by `scripts/test_receipts.py`; each case runs in an isolated `SEATBELT_HOME` and a fresh process.

| # | Scenario | Expected |
|---|---|---|
| 1 | Delete a single tracked file | T1 trash card, restore exact bytes and mode |
| 2 | Delete a directory tree | All files restored from manifest |
| 3 | Generated artifact (`node_modules`) | Safe exception still produces token + receipt |
| 4 | `git reset --hard` with uncommitted work | Branch ref restored and stash applied |
| 5 | Force-push to a feature branch with a local bare remote | Remote ref restored; drift check passes |
| 6 | SQLite `DROP TABLE` with `--db` | Backup table created; rows restored |
| 7 | T4 force-push to `main` | No blast preparation, no token, no receipt |
| 8 | Drift: destination recreated with different content | Undo refuses, writes `verified: false` receipt |
| 9 | Receipt chain | Valid chain verifies; tampering fails verification |
| 10 | Fresh session + 7-day expiry | Token survives process restart; `prune` removes expired manifests |

Pass criteria: every restore matches the pre-state, zero T4 tokens issued, drift never overwritten, chain verification detects edits.

Manual probes worth repeating in a real repo:
- Force-push where someone else updated the remote after the backup → undo must refuse.
- Terraform destroy with a saved plan → state restored, apply is opt-in.
- Secret-path backups → manifest marked `contains_secrets`, directory mode `0700`.
