"""Shared test fixtures for fgeo v0.2 tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from fgeo.database import Database


@pytest.fixture
def fgeo_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create an isolated ~/.fgeo directory for testing."""
    home = tmp_path / ".fgeo"
    home.mkdir()
    (home / "skills").mkdir()

    db_file = home / "fgeo.db"
    config_file = home / "config.yaml"

    # Patch constants so all code uses the tmp dir
    monkeypatch.setattr("fgeo.constants.FGEO_HOME", home)
    monkeypatch.setattr("fgeo.constants.FGEO_CONFIG_FILE", config_file)
    monkeypatch.setattr("fgeo.constants.FGEO_SKILLS_DIR", home / "skills")
    monkeypatch.setattr("fgeo.database.FGEO_DB_FILE", db_file)

    # Also patch in modules that import from constants at module level
    monkeypatch.setattr("fgeo.config.FGEO_CONFIG_FILE", config_file)

    # Patch init module's local imports (imported at module level)
    monkeypatch.setattr("fgeo.commands.init.FGEO_HOME", home)
    monkeypatch.setattr("fgeo.commands.init.FGEO_SKILLS_DIR", home / "skills")
    monkeypatch.setattr("fgeo.commands.init.FGEO_CONFIG_FILE", config_file)
    monkeypatch.setattr("fgeo.commands.init.FGEO_DB_FILE", db_file)

    return home


@pytest.fixture
def db(fgeo_home: Path) -> Database:
    """Create a Database instance backed by isolated fgeo_home."""
    db_file = fgeo_home / "fgeo.db"
    database = Database(db_path=db_file)
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Create a sample workspace with .git and markdown files."""
    ws = tmp_path / "project-a"
    ws.mkdir()
    (ws / ".git").mkdir()

    article = ws / "hello-world.md"
    article.write_text(
        "---\n"
        "title: Hello World\n"
        "description: A test article about hello world\n"
        "category: what-is\n"
        "tags: [test, hello]\n"
        "---\n\n"
        "# Hello World\n\n"
        "This is a test article.\n"
    )

    bare = ws / "bare-article.md"
    bare.write_text("# My Bare Article\n\nNo frontmatter here.\n")

    video = ws / "demo.mp4"
    video.write_bytes(b"\x00" * 100)

    return ws


@pytest.fixture
def seeded_db(db: Database) -> Database:
    """Database pre-seeded with a project, goal, platforms, plan, and content."""
    db.create_project("fcontext", description="AI context manager")
    db.add_goal("fcontext", "让所有人了解fcontext")
    db.add_platform("fcontext", "twitter", directions="build-in-public,hot-takes", pace="3/周")
    db.add_platform("fcontext", "devto", directions="architecture", pace="2/月")

    goals = db.list_goals("fcontext")
    db.create_plan("fcontext", "cold-start", goal_id=goals[0]["id"], strategy="英文社区渗透")

    db.assign_plan_platform("fcontext", "cold-start", "twitter", direction="build-in-public", target=12)
    db.assign_plan_platform("fcontext", "cold-start", "devto", direction="architecture", target=3)

    db.register_content(
        title="Why I built fcontext",
        project_name="fcontext",
        platform_name="twitter",
        plan_name="cold-start",
        direction="build-in-public",
        content_type="thread",
        status="published",
    )
    db.register_content(
        title="fcontext architecture deep dive",
        project_name="fcontext",
        platform_name="devto",
        plan_name="cold-start",
        direction="architecture",
        content_type="article",
        status="draft",
    )
    return db
