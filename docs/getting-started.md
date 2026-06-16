# Getting Started

## Install

```bash
pip install fgeo
```

Initialize the global fgeo home:

```bash
fgeo init
```

This creates `~/.fgeo/`, including the SQLite database and config file used as
the user-level content registry.

## Enable an Agent

Inside the product workspace:

```bash
fgeo enable copilot
```

Use any supported agent name:

```bash
fgeo enable claude
fgeo enable cursor
fgeo enable codex
```

The enable command does two things:

1. Ensures fcontext is initialized and enabled for the same agent.
2. Writes fgeo instructions into the agent's native rules or skills location.

## Create a Project

```bash
fgeo project create fcontext --desc "AI context manager"
fgeo project list
fgeo project show fcontext
```

Projects are the main targets of promotion. A project can be a product, a
personal brand, an open source library, or a campaign.

## Add Goal, Platform, and Plan

```bash
fgeo goal add fcontext "Help developers understand fcontext"

fgeo platform add fcontext devto \
  --directions "tutorial,architecture" \
  --pace "2/month"

fgeo plan create fcontext cold-start \
  --strategy "Developer community launch"

fgeo plan assign fcontext cold-start devto \
  --direction tutorial \
  --target 3
```

## Register Content

```bash
fgeo content register docs/first-post.md \
  --project fcontext \
  --platform devto \
  --plan cold-start \
  --direction tutorial \
  --type article \
  --status draft
```

Then inspect progress:

```bash
fgeo status fcontext
fgeo content list --project fcontext
```

## Publish

```bash
fgeo publish list --project fcontext
fgeo publish content <content-id>
```

The publish command detects the content platform and routes to the matching
publisher.

