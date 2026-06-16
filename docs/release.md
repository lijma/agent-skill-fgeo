# Release Process

fgeo uses `setuptools-scm` for versioning. The package version is derived from
the Git tag that triggers the release workflow.

## Tag Format

Use either:

```bash
git tag v0.6.0
git push origin v0.6.0
```

or:

```bash
git tag 0.6.0
git push origin 0.6.0
```

`v0.6.0` builds package version `0.6.0`.

## Release Workflow

The GitHub Action runs on tag pushes matching `v*` or `[0-9]*`.

It performs:

1. test matrix on Python 3.10, 3.12, and 3.13
2. package build with `python -m build`
3. PyPI publish through trusted publishing

## Required Repository Setup

For PyPI publishing, configure trusted publishing on PyPI for:

- repository: `lijma/agent-skill-fgeo`
- workflow: `release.yml`
- environment: none, unless you add one later

No PyPI token is needed when trusted publishing is configured.

