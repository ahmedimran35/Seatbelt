# Command catalog

Quick reference for patterns in `assets/risk-patterns.json`. The classifier uses the JSON; this file explains the decisions and helps when Python is unavailable.

## T4 — always deny

| Command | Why | Safe alternative |
|---|---|---|
| `rm -rf /`, `rm -rf ~`, `rm -rf $HOME`, `rm -rf /*` | Recursive delete of root/home | Ask which specific generated dir to remove |
| `git push --force origin main`, `git push -f origin master`, `git push origin +main:main` | Rewrites shared default branch | Feature branch + PR; `--force-with-lease` on your own feature branch |
| `dd if=… of=/dev/…`, `mkfs`, `Format-Volume`, `Clear-Disk` | Destroys a device | — (user must do it themselves) |
| `curl … \| sh`, `wget … \| bash`, `iex`, `powershell -EncodedCommand` | Opaque remote/encoded code | Download, inspect, then run |
| `:(){ :|:& };:` | Fork bomb | — |

## T3 — catastrophic

| Command | Why | Safer option |
|---|---|---|
| `rm -rf <broad path>` | Recursive delete | Trash; narrow to generated dirs |
| `DROP TABLE/DATABASE/SCHEMA`, `TRUNCATE TABLE` | Destroys data | Rename/archive, backup, expand-then-contract |
| `DELETE FROM t` / `UPDATE t` without `WHERE` | All rows | Add `WHERE`; `SELECT count(*)` first |
| `git push --delete/--mirror/--all`, `:branch` refspec | Removes remote refs | Archive first |
| `git push --no-verify` | Skips checks | Run checks; push normally |
| `git stash drop/clear`, `git reflog expire/delete`, `git gc --prune` | Destroys recovery history | Keep refs; back up `refs/stash` |
| `git worktree remove --force` | Removes uncommitted work | Commit or stash first |
| `find . -delete`, `find . -exec rm …` | Deletion without explicit list | Same `find` with `-print` first |
| `python -c`, `node -e`, `perl -e`, `php -r` | Inline code cannot be inspected | Show the code; use a reviewed file |
| `cat .env`, `gh auth token`, reads of `~/.ssh`, `credentials` | Secret exposure | Confirm the file is not secret |
| `chmod 777` | World-writable | Narrowest mode that works |
| `npm publish`, `gem push` | Public release | `npm pack --dry-run` first |
| `terraform destroy` | Infrastructure teardown | `terraform plan -destroy`, state backup |

## T2 — risky

| Command | Why | Safer option |
|---|---|---|
| `git push --force` / `-f` to a feature branch | Rewrites remote history | `--force-with-lease`, revert commit |
| `git reset --hard` | Discards working-tree changes | `git stash push -u` first |
| `git clean -fd` | Deletes untracked files | `git clean -nd` preview; trash |
| `git checkout --`, `git restore --`, `git checkout .` | Discards local edits | `git stash push -- <path>` |
| `git branch -D` | Deletes unmerged branch | `git branch -d` |
| `kubectl delete`, `helm uninstall` | Removes live resources | Save manifest, re-apply from VCS |
| `docker system prune`, `docker volume rm` | Removes images/volumes | `docker system df`; volumes hold data |
| `chmod -R`, `chown -R` | Recursive metadata change | Capture original modes |
| `kill -9`, `Stop-Process -Force` | Unclean shutdown | `kill -TERM`, wait |
| `truncate -s`, `Clear-Content` | Discards file content | Back up first |
| `sudo`, `runas` | Elevated privileges | Scope narrowly |
| `--force`, `--yes`, `--assume-yes` | Bypasses normal checks | Re-run without flag after confirmation |

## T1 / T0 — reversible and safe

| Command | Tier | Note |
|---|---|---|
| `rm <file>` | T1 | Restore from git or backup |
| `rm -rf node_modules\|dist\|build\|.next\|__pycache__\|.cache\|coverage` | T1 | Safe exception: generated artifact |
| `git push --dry-run`, `git clean -n`, `terraform plan`, `npm pack --dry-run` | T0 | Read-only preview |
| `git status`, `git log`, `git diff`, reads, tests | T0 | No prompt |

## PowerShell and cmd

| Command | Tier |
|---|---|
| `Remove-Item`/`ri`/`del`/`erase` + `-Recurse`/`-Force` | T3; T4 at drive root |
| `Clear-Disk`, `Format-Volume`, `iex`, `-EncodedCommand` | T4 |
| `Stop-Process -Force`, `Clear-Content` | T2 |
| `rd /s`, `rmdir /s` (cmd) | T3 |

Static string matching cannot see runtime-built commands. Treat unresolvable PowerShell as risky and ask.

## Adding a pattern

Edit `assets/risk-patterns.json` (`id`, `tier`, `regex`, `reasons`, `preview`, `rollback`; optional `"scope": "command"`), add a case to `scripts/test_risk_check.py`, and rerun both suites. Keep `SKILL.md` unchanged.
