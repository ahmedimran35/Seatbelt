# Rollback playbook

Offer a rollback before confirming any T2/T3 action. If no rollback exists, say so plainly — that is a reason to ask for stronger consent, not to skip the question.

## Contents
- Git history
- Files and directories
- Databases
- Processes and containers
- Infrastructure
- Reporting after execution

## Git history

**Before a force-push or reset:**
```bash
git stash push -u -m "seatbelt: before destructive op"
git branch backup/pre-force-push HEAD
git log --oneline origin/<branch>..HEAD
```
**Undo a force-push:** recreate the remote ref from the backup branch, or from reflog:
```bash
git reflog --date=iso | head -30
git push origin backup/pre-force-push:refs/heads/<branch>
```
**Undo a hard reset:** `git reset --hard <reflog-sha>`; restore uncommitted work from the stash.

## Files and directories

- Prefer `trash <path>` (or `mv <path> ~/.Trash/`) over `rm` for user-created files.
- Before deleting tracked files, confirm `git status --short -- <path>` is clean.
- Before deleting untracked files, back them up: `tar -czf ~/backup/$(date +%F)-seatbelt.tar.gz <paths>`.
- Never promise recovery of untracked files without an actual backup.

## Databases

**Before any DROP/TRUNCATE or destructive migration:**
```sql
SELECT count(*) FROM <table>;
CREATE TABLE <table>_backup AS SELECT * FROM <table>;  -- where practical
```
- Run destructive migrations inside a transaction when the engine supports it.
- Keep the reverse migration tested, not just written.
- Confirm row counts after the change with a read-only query.

## Processes and containers

- Use `kill -TERM`, wait, then `kill -9` only if necessary. Note in-flight work may be lost.
- Before `docker rm -f`, run `docker stop` so the process can shut down cleanly.
- Before `kubectl delete`, save the live manifest with `kubectl get <resource> <name> -o yaml > backup.yaml` so it can be re-applied.

## Infrastructure

- Always `terraform plan -destroy` and keep the plan output plus `terraform.tfstate` backup.
- Confirm the workspace: `terraform workspace show`. Deleting in the wrong workspace is a common T3 incident.
- Prefer disabling or scaling to zero before deleting, so the change is reversible.

## Reporting after execution

End with a short blast log, for example:

> "Done. Deleted `dist/` (18 files, moved to trash). Created `backup/pre-force-push`. Force-pushed `feature-x`; 3 commits rewritten. No other changes."

If verification fails, say exactly what failed and do not claim success.
