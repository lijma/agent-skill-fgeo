# Agent Integrations

`fgeo enable <agent>` registers fgeo instructions in the current workspace and
enables fcontext for the same agent.

## Supported Agents

| Agent | Command | fgeo files written |
| --- | --- | --- |
| GitHub Copilot | `fgeo enable copilot` | `.github/instructions/fgeo.instructions.md`, `.github/skills/fgeo/SKILL.md` |
| Claude | `fgeo enable claude` | `.claude/rules/fgeo.md`, `.claude/skills/fgeo/SKILL.md` |
| Cursor | `fgeo enable cursor` | `.cursor/rules/fgeo.md`, `.cursor/skills/fgeo/SKILL.md` |
| Trae | `fgeo enable trae` | `.trae/rules/fgeo.md`, `.trae/skills/fgeo/SKILL.md` |
| Qwen | `fgeo enable qwen` | `.qwen/rules/fgeo.md`, `.qwen/skills/fgeo/SKILL.md` |
| Kiro | `fgeo enable kiro` | `.kiro/steering/fgeo.md`, `.kiro/skills/fgeo/SKILL.md` |
| OpenCode | `fgeo enable opencode` | Claude-compatible files |
| OpenClaw | `fgeo enable openclaw` | `skills/fgeo/SKILL.md` |
| Zed | `fgeo enable zed` | `.agents/skills/fgeo/SKILL.md` |
| Pi | `fgeo enable pi` | `.pi/skills/fgeo/SKILL.md` |
| AntiGravity | `fgeo enable antigravity` | `.agent/rules/fgeo.md`, `.agent/skills/fgeo/SKILL.md` |
| Codex | `fgeo enable codex` | `.codex/skills/fgeo/SKILL.md` |

Aliases:

- `codex-agent`
- `codex_agent`

Both map to `codex`.

## Agent Workflow Rules

The generated fgeo instruction tells agents to:

1. Load fgeo and fcontext state before acting.
2. Treat strategic choices as consultant work: propose, wait for confirmation,
   then execute.
3. Gate content creation behind brand, platform, and platform style checks.
4. Register finished content only after the user approves the saved file.
5. Use `fgeo publish content <id>` for publish intent instead of merely setting
   status to published.
6. Surface missing CLI capabilities as feature gaps instead of editing the
   database directly.

## List Status

```bash
fgeo enable list
```

This shows which agents are already registered in `~/.fgeo/config.yaml`.

