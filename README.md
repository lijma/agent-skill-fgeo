# fgeo

Generative Engine Optimization CLI for AI-assisted go-to-market work.

fgeo helps product builders turn product knowledge into a managed content system:
projects, goals, plans, platforms, content assets, and publishing tasks all live in
one local registry.

## Quick Start

```bash
pip install fgeo

fgeo init
fgeo enable copilot

fgeo project create fcontext --desc "AI context manager"
fgeo goal add fcontext "Help developers understand fcontext"
fgeo platform add fcontext devto --directions "tutorial,architecture" --pace "2/month"
fgeo plan create fcontext cold-start --strategy "Developer community launch"
fgeo plan assign fcontext cold-start devto --direction tutorial --target 3

fgeo content register docs/first-post.md \
  --project fcontext \
  --platform devto \
  --plan cold-start \
  --direction tutorial \
  --type article \
  --status draft

fgeo status fcontext
```

## What fgeo Manages

```text
Project -> Goal -> Plan -> Platform -> Content -> Publish Task
```

- Project: a product, personal IP, or campaign target.
- Goal: what success looks like.
- Plan: the go-to-market strategy and target counts.
- Platform: a distribution channel with its own directions and cadence.
- Content: one platform-native content asset.
- Publish task: the handoff between draft content and live distribution.

## Supported Agent Integrations

`fgeo enable <agent>` writes fgeo instructions into each agent's native location
and also enables fcontext for the same workspace.

Supported agents:

`copilot`, `claude`, `cursor`, `trae`, `qwen`, `kiro`, `opencode`,
`openclaw`, `zed`, `pi`, `antigravity`, and `codex`.

## Documentation

The full documentation site is built with MkDocs:

```bash
pip install -e ".[dev]"
mkdocs serve
```

Docs source lives in `docs/`.

