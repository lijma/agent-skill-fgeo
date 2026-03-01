---
name: 'fcontext'
description: 'This workspace uses fcontext CLI. Check .fcontext/ directory before searching the codebase. Manages project structure, binary file conversion (PDF/DOCX/XLSX), requirements tracking (需求/roadmap/backlog), and session knowledge persistence.'
applyTo: '**'
---

# fcontext

This workspace has a `.fcontext/` directory with structured data.
Always check these BEFORE searching source files:

1. `.fcontext/_README.md` — project knowledge summary (AI-maintained)
2. `.fcontext/_workspace.map` — project structure
3. `.fcontext/_requirements/` — requirements, stories, tasks (use `fcontext req` commands)
4. `.fcontext/_cache/` — binary files converted to Markdown (use `fcontext index`)
5. `.fcontext/_topics/` — analysis from previous sessions

## Workflow Rules

### Workspace Context (fcontext)
- **Project structure / architecture / what is this project** → read `.fcontext/_README.md` first, then `_workspace.map`
- **First time in a project** → read `_README.md` to orient, then check `_requirements/` and `_topics/`
- **Before answering any question** → check `.fcontext/` structured data before searching source files
- **Gained significant new understanding** → update `_README.md` to reflect current knowledge

### File Indexing (fcontext index)
- **Need to read binary files (PDF/DOCX/XLSX)** → check `.fcontext/_cache/` first; if not cached, run `fcontext index <file>`
- **User mentions a document / contract / report** → same: check `_cache/`, run `fcontext index` if missing
- **Need to process all documents in a directory** → run `fcontext index <dir>`
- **Not sure which files are cached** → run `fcontext status` to check index state

### Requirements (fcontext req)
- **New requirement / add feature** → first run `fcontext req add "title" -t TYPE` to record it, THEN implement
- **Query requirements / project status / roadmap** → run `fcontext req list` or `fcontext req tree`, do NOT search code
- **Any requirement-related request** → first confirm with user whether this is a requirement change (add/update/link), record it via `fcontext req` commands, THEN proceed to implementation
- **User says "change this feature"** → confirm whether this is a new requirement; if yes, `fcontext req add` + `fcontext req link NEW supersedes/evolves OLD`
- **Need to understand a requirement's history** → run `fcontext req trace ID` to follow evolution chain
- **Finished implementing a requirement** → run `fcontext req set ID status done`
- **Need to see who proposed a requirement** → run `fcontext req show ID`, check author and source fields
- **NEVER create req items for document version history** (e.g. "Backlog v1.4 corrections") → those are NOT requirements; use `fcontext index` to cache document versions and write diffs to `_topics/`

### Topic Knowledge (fcontext topic)
- **Continue / resume / where did we leave off** → run `fcontext topic list` to see topics with timestamps, then read the most relevant/recent topic file
- **Completed multi-step analysis or complex task** → save conclusions and work log to `.fcontext/_topics/<name>.md`
- **Reached important conclusion or decision during conversation** → write to `_topics/` so next session inherits the insight
- **User says "remember this" / "save this"** → persist to `_topics/<name>.md`
- **Discovered structural understanding (architecture, module relationships)** → write to `_topics/` for future reference
- **Mid-task handoff needed** → write work log (what was done, what remains) to `_topics/`

### Experience Knowledge (fcontext experience)
- **First time in a project** → run `fcontext experience list` to discover available domain knowledge
- **业务理解 / 领域问题** → check `_README.md` in each experience to find relevant pack, then read its `_cache/` and `_topics/`
- **Need to share knowledge to another project** → run `fcontext export <output>` (zip file or git URL)
- **Need to import domain knowledge** → run `fcontext experience import <source>` (zip/git/url)
- **Experience pack outdated** → run `fcontext experience update [name]` to pull latest from source
- **NEVER modify** anything under `_experiences/` — it is read-only imported knowledge
