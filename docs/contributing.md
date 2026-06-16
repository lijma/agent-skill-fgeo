# Contributing

## Development Setup

```bash
git clone git@github.com:lijma/agent-skill-fgeo.git
cd agent-skill-fgeo

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,publish]"
```

## Run Tests

```bash
pytest --cov=fgeo --cov-report=term-missing --cov-fail-under=100
```

The project currently expects 100 percent unit test coverage.

## Build Docs

```bash
mkdocs build --strict
mkdocs serve
```

## Build Package

```bash
python -m build
```

Versions are generated from Git tags through `setuptools-scm`; do not manually
edit a static version in `pyproject.toml`.

