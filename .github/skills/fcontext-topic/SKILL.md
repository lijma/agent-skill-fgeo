---
name: fcontext-topic
description: Record important conclusions, discoveries, and work logs from AI sessions into .fcontext/_topics/. Use after completing non-trivial analysis or multi-step tasks worth preserving.
---

# Topic Knowledge — Recording Guide

Write conclusions and work logs to `.fcontext/_topics/<name>.md` so the next session starts with full context instead of from zero.

## When to Write

- Key conclusions or decisions reached during conversation
- Work log for multi-step tasks (what was done, what remains)
- Cross-document analysis results (comparisons, gap analysis)
- Structural understanding discovered (architecture, module relationships)
- User explicitly asks to save or persist findings

## When NOT to Write

- Simple Q&A (one-turn answers)
- Single-file edits (result lives in the code)
- Content already covered by an existing topic (update it instead)

## Commands

```
fcontext topic list                   # list all topics
fcontext topic show <name>            # show topic content
fcontext topic clean                  # remove empty topic files
```
