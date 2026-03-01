---
name: fcontext-req
description: Track project requirements, stories, tasks, and bugs. Use when user asks about requirements, 需求, roadmap, backlog, project status, or wants to add/update/link items.
---

# Requirements Management

Data lives in `.fcontext/_requirements/`. Run CLI commands — do NOT parse CSV manually.

## Commands

```
fcontext req list                     # all items (--type, --status filters)
fcontext req tree                     # hierarchy view
fcontext req board                    # kanban by status
fcontext req show ID                  # details + changelog
fcontext req add "title" -t TYPE      # types: roadmap/epic/requirement/story/task/bug
fcontext req set ID field value       # update (auto-logs changelog)
fcontext req link ID TYPE TARGET      # link types: supersedes/evolves/relates/blocks
fcontext req trace ID                 # follow evolution chain
fcontext req comment ID "msg"         # append comment
```

## Provenance

Add `--author` and `--source` on `req add` to record who proposed it and from which document.

## Evolution

Requirements are immutable. When a requirement changes:
1. Create a new one with `req add`
2. Link it: `fcontext req link NEW supersedes OLD` (or `evolves`)
3. Trace history: `fcontext req trace ID`

Link types: `supersedes` (replaces), `evolves` (iterates on), `relates`, `blocks`

## What NOT to Track as Requirements

Only create requirement items for **actionable work** (things to build, fix, or decide).

Do NOT create req items for:
- Document version history ("Backlog v1.4 corrections", "v2.0 updates") → use `fcontext index` to cache each version, write diffs to `_topics/`
- Meeting notes or discussion logs → write to `_topics/`
- Changelog entries of external documents → write to `_topics/`

When importing from external backlogs, extract the **actual requirements** (what to build), not the document's revision history.

## Data Structure

```
.fcontext/_requirements/
  items.csv      — id, type, title, status, priority, parent, assignee, tags,
                   created, updated, author, source, links
  _backlog.md    — auto-generated summary (read-only)
  docs/<ID>.md   — detailed description + changelog per item
```
