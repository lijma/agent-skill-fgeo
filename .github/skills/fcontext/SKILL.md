---
name: fcontext
description: Workspace structure overview. Read .fcontext/_workspace.map to understand project layout, directories, and file types before answering questions about the project.
---

# Workspace Context

Read `.fcontext/_README.md` for a project knowledge summary, then `_workspace.map` for structure.

This workspace uses `fcontext` CLI. The `.fcontext/` directory contains:

- `_README.md` — project knowledge summary (**AI maintains this**)
- `_workspace.map` — project structure overview (auto-generated)
- `_cache/` — binary files converted to Markdown
- `_topics/` — accumulated analysis from previous sessions
- `_requirements/` — requirements, stories, tasks, bugs
- `_experiences/` — imported domain knowledge packs (read-only)

## Maintaining _README.md

After gaining significant new understanding about the project (domain concepts, architecture, business rules), update `.fcontext/_README.md` to reflect current knowledge. This file is the first thing the next AI session reads.

## General Commands

```
fcontext init                         # initialize .fcontext/
fcontext enable <agent>               # activate agent (copilot/claude/cursor/trae/opencode)
fcontext status                       # index statistics
fcontext clean                        # clear cache
fcontext reset                        # delete all .fcontext/ data
fcontext experience list              # show imported experience packs
fcontext experience import <source>   # import experience (zip/git/url)
fcontext experience remove <name>     # remove an experience pack
fcontext experience update [name]     # update from original source
fcontext export <output>              # export knowledge (zip or git remote)
```
