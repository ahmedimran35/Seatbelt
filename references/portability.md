# Install and portability

The core (`SKILL.md` plus `references/`, `scripts/`, `assets/`) uses the open Agent Skills format. It works in agents that read `SKILL.md` folders. The PreToolUse hook is a Claude Code add-on.

## Where each agent looks

| Agent | Personal folder | Project folder |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenCode | `~/.agents/skills/` (also `~/.config/opencode/skills/`) | `.opencode/skills/`, `.agents/skills/` |
| OpenAI Codex | `~/.agents/skills/` | `.agents/skills/` |
| Cursor | `~/.agents/skills/`, `~/.cursor/skills/` | `.agents/skills/`, `.cursor/skills/` |
| GitHub Copilot | `~/.copilot/skills/`, `~/.agents/skills/` | `.github/skills/`, `.agents/skills/` |

Claude Code's docs do not promise symlink support. Use a real copy for Claude Code; verify a link before relying on it elsewhere.

## Install commands

```bash
# Source of truth lives in /Users/imran/skills develop/seatbelt
cp -R "/Users/imran/skills develop/seatbelt" ~/.agents/skills/seatbelt
cp -R "/Users/imran/skills develop/seatbelt" ~/.claude/skills/seatbelt

# Optional Claude Code enforcement
python3 ~/.claude/skills/seatbelt/scripts/install_hook.py install --scope project --mode full
```

Do not overwrite an existing `seatbelt/` folder without inspecting it first.

## Verification

1. Confirm the skill appears in each agent's skill list.
2. Classifier: `python3 ~/.agents/skills/seatbelt/scripts/risk_check.py --command "git push --force origin main" --format text`
3. Classifier suite: `python3 ~/.agents/skills/seatbelt/scripts/test_risk_check.py`
4. Hook suite: `python3 ~/.agents/skills/seatbelt/scripts/test_hook.py`
5. Hook self-test: `python3 ~/.claude/skills/seatbelt/scripts/hook.py test`
6. Claude Code: `/hooks` should list the Seatbelt entry.

## Invoking the skill

Skills and slash commands are different things. In OpenCode, a skill is advertised to the model and loaded with the `skill` tool; it does not become `/seatbelt` automatically.

| Agent | Automatic trigger | Direct invocation |
|---|---|---|
| OpenCode | Model matches the `description` | Mention `@seatbelt` in your prompt, or run `/seatbelt ultra` using `~/.config/opencode/commands/seatbelt.md` |
| Claude Code | Model matches the `description` | `/seatbelt` is generated from the skill name |
| Codex | Model matches the `description` | `/skills` then select, or mention `$seatbelt` |
| Cursor | Model matches the `description` | `/` menu lists skills in Agent chat |

OpenCode command behaviour:

```text
/seatbelt            → full (default)
/seatbelt lite       → warn-only mode
/seatbelt ultra      → hand off every command above T0
/seatbelt lockdown   → only T0 runs
```

## Agent-specific extras (optional)

Do not put these in the portable core:

- Claude Code `PreToolUse` hooks, permissions deny rules, `allowed-tools`, slash-command arguments.
- Codex `agents/openai.yaml` display names and MCP dependencies.
- Cursor/Codex hook wiring for `scripts/hook.py`.

Keep `name` and `description` identical everywhere — they are what every agent reads for discovery.

## Updating

Bump `metadata.version` in `SKILL.md`, add an entry to `CHANGELOG.md`, re-copy to install folders, and rerun both suites after any change to `assets/risk-patterns.json` or `scripts/`.
