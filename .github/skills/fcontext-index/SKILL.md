---
name: fcontext-index
description: Convert binary files (PDF, DOCX, XLSX) to Markdown and cache in .fcontext/_cache/. Use when user references a binary document or needs to read non-text files.
---

# Binary File Indexing

Binary files are converted to Markdown and cached in `.fcontext/_cache/`.

## Usage

Check `_cache/` first. If the file is not cached:

```
fcontext index <file>                 # convert one file
fcontext index <dir>                  # convert all in directory
```

Do not use other conversion tools — `fcontext index` caches results for reuse across sessions.

The `_index.json` maps each source file to its cached `.md` with mtime tracking.
