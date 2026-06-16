# Command Reference

## Setup

```bash
fgeo init
fgeo enable <agent>
fgeo enable list
fgeo --version
```

## Project

```bash
fgeo project create <name> [--desc TEXT] [--workspace PATH]
fgeo project list [--status active|archived]
fgeo project show <name-or-id>
fgeo project set <name-or-id> <field> <value>
fgeo project remove <name-or-id> [--force]
```

## Goal

```bash
fgeo goal add <project> "goal title"
fgeo goal list <project>
fgeo goal set <goal-id> <field> <value>
```

Goal status values include `active`, `achieved`, `paused`, and `abandoned`.

## Platform

```bash
fgeo platform add <project> <name> [--directions TEXT] [--pace TEXT]
fgeo platform list <project>
fgeo platform show <project> <name>
fgeo platform set <project> <name> <field> <value>
fgeo platform remove <project> <name> [--force]
```

Common platform fields:

- `directions`
- `pace`
- `status`
- `publish_url`
- `bsky_handle`
- `platform_secret`
- `last_published_at`

## Plan

```bash
fgeo plan create <project> <name> [--strategy TEXT] [--goal GOAL_ID]
fgeo plan list <project> [--status draft|active|completed|archived]
fgeo plan show <project> <name>
fgeo plan assign <project> <plan> <platform> [--direction TEXT] [--target N]
fgeo plan set <project> <name> <field> <value>
fgeo plan remove <project> <name> [--force]
```

## Content

```bash
fgeo content register <file> \
  [--title TEXT] \
  [--project NAME] \
  [--platform NAME] \
  [--plan NAME] \
  [--direction TEXT] \
  [--tags TEXT] \
  [--desc TEXT] \
  [--type article|video|slide|thread|short] \
  [--status planned|draft|review|published]

fgeo content list [--project NAME] [--platform NAME] [--status STATUS] [--direction TEXT] [--no-plan]
fgeo content show <content-id>
fgeo content set <content-id> <field> <value>
fgeo content assign-plan <project> <plan> [--platform NAME] [--status STATUS]
fgeo content remove <content-id> [--force]
```

## Brand

```bash
fgeo brand show
fgeo brand set <field> <value>
fgeo brand init
```

Brand fields:

- `name`
- `positioning`
- `voice`
- `core_values`
- `topics`

## Style

```bash
fgeo style add <platform> [--desc TEXT] [--formula TEXT] [--tone TEXT] [--format TEXT]
fgeo style list
fgeo style show <platform>
fgeo style set <platform> <field> <value>
```

## Publish

```bash
fgeo publish list [--status draft] [--project NAME] [--platform NAME]
fgeo publish content <content-id> [--blog-dir PATH] [--url URL] [--force]
fgeo publish task list [--status pr_open|merged|failed]
fgeo publish task show <task-id>
fgeo publish task done <task-id>
```

## Dashboard

```bash
fgeo status <project> [--platform NAME]
```

