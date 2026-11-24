# Known gaps

Be honest about these. Seatbelt reads command text; it is not a sandbox, not a policy boundary, and not a substitute for scoped credentials, branch protection, or a container.

## The classifier

- It errs toward allowing when it cannot resolve a command.
- It does not see inside scripts, Makefiles, npm scripts, or git aliases (`npm run clean`, `./deploy.sh`, `git cleanall`).
- It does not resolve paths built from unset variables (`rm -rf "$DIR/"`) or expanded globs; those are T3 by the unknown-target rule only if you pass `--target-known no`.
- `find -delete` and `find -exec rm` are matched, but `find | xargs rm` shapes may need manual classification.
- It cannot inspect dynamically built PowerShell strings; unresolvable PowerShell should be treated as T3.
- Static tiers are broad: `rm -rf` starts at T3 even for a narrow generated dir. Safe exceptions and sandbox bumps lower it, and the reason must be shown in the preview.

## The hook

- Only Claude Code's `Bash`, `PowerShell`, `Edit`, `Write`, and `MultiEdit` events are enforced. The `Read` tool and MCP tools are not covered.
- Hooks in settings files can tighten but not loosen permission rules. A user can remove the hook; an admin can disable user hooks with `allowManagedHooksOnly`.
- The `if`/matcher filter is best-effort; the hook handler itself sees the full command when it runs.
- T3 asks via Claude Code's permission prompt; it cannot collect the typed `GO` the conversational skill requires. The typed `GO` is a separate, stricter layer.
- A `deny` from the hook holds in `bypassPermissions`, but a user who controls machine settings can uninstall it.

## Not covered at all

- Network exfiltration that does not use a known pattern.
- Credential exposure through a tool other than Bash/Edit/Write.
- What happens after a command is authorised (the command itself may be compromised).
- Terraform/helm state corruption that looks like a normal `apply`.
- Multi-agent collusion where one agent writes a script another agent runs.

## For a hard boundary

Use a container or VM, remote branch protection, scoped read-only credentials, and a filesystem-level backup. Tell the user this when they ask whether Seatbelt is a security tool.

## Scanner note

Security scanners flag rule tables and test files because they must contain the dangerous command strings. `SKILL.md` and `references/` are prose. If a scanner complains, point it at this file.
