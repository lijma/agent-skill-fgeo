"""Tests for fgeo.database — SQLite data layer."""

from __future__ import annotations

import pytest

from fgeo.database import Database, _make_id


class TestSchemaInit:
    def test_init_creates_tables(self, db: Database):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "projects" in names
        assert "goals" in names
        assert "platforms" in names
        assert "plans" in names
        assert "plan_platforms" in names
        assert "contents" in names
        assert "schema_meta" in names

    def test_schema_version(self, db: Database):
        row = db.conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        assert row["value"] == "0.4.0"

    def test_init_idempotent(self, db: Database):
        db.init_schema()
        db.init_schema()
        tables = db.conn.execute("SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table'").fetchone()
        assert tables["cnt"] >= 7


class TestProjects:
    def test_create_project(self, db: Database):
        proj = db.create_project("fcontext", description="AI context manager")
        assert proj["name"] == "fcontext"
        assert proj["description"] == "AI context manager"
        assert proj["status"] == "active"
        assert proj["id"].startswith("proj-")

    def test_create_duplicate_fails(self, db: Database):
        db.create_project("fcontext")
        with pytest.raises(Exception):
            db.create_project("fcontext")

    def test_list_projects(self, db: Database):
        db.create_project("proj-a")
        db.create_project("proj-b")
        projects = db.list_projects()
        assert len(projects) == 2

    def test_list_projects_filter_status(self, db: Database):
        db.create_project("proj-a")
        db.create_project("proj-b")
        db.update_project("proj-b", "status", "archived")
        active = db.list_projects(status="active")
        assert len(active) == 1
        assert active[0]["name"] == "proj-a"

    def test_get_project_by_name(self, db: Database):
        db.create_project("fcontext")
        proj = db.get_project("fcontext")
        assert proj is not None
        assert proj["name"] == "fcontext"

    def test_get_project_by_id(self, db: Database):
        created = db.create_project("fcontext")
        proj = db.get_project(created["id"])
        assert proj is not None
        assert proj["name"] == "fcontext"

    def test_get_project_not_found(self, db: Database):
        assert db.get_project("nonexistent") is None

    def test_update_project(self, db: Database):
        db.create_project("fcontext")
        result = db.update_project("fcontext", "description", "New desc")
        assert result["description"] == "New desc"

    def test_update_project_invalid_field(self, db: Database):
        db.create_project("fcontext")
        assert db.update_project("fcontext", "invalid_field", "val") is None

    def test_delete_project_not_found(self, db: Database):
        assert db.delete_project("nonexistent") is None

    def test_delete_project_empty(self, db: Database):
        db.create_project("fcontext")
        counts = db.delete_project("fcontext")
        assert counts == {"contents": 0, "plans": 0, "platforms": 0, "goals": 0}
        assert db.get_project("fcontext") is None

    def test_delete_project_cascades_all(self, db: Database):
        db.create_project("fcontext", description="test")
        db.add_goal("fcontext", "Goal A")
        db.add_goal("fcontext", "Goal B")
        db.add_platform("fcontext", "twitter", directions="bip")
        db.add_platform("fcontext", "devto", directions="tutorial")
        goal = db.add_goal("fcontext", "Goal C")
        db.create_plan("fcontext", "cold-start", strategy="test", goal_id=goal["id"])
        # Register content linked to project
        db.register_content(
            source_path="/tmp/test.md", title="Test",
            project_name="fcontext", platform_name="twitter",
        )
        counts = db.delete_project("fcontext")
        assert counts["goals"] == 3
        assert counts["platforms"] == 2
        assert counts["plans"] == 1
        assert counts["contents"] == 1
        # Verify everything is gone
        assert db.get_project("fcontext") is None
        assert db.list_goals("fcontext") == []
        assert db.list_platforms("fcontext") == []
        assert db.list_plans("fcontext") == []
        assert db.list_contents() == []

    def test_delete_project_by_id(self, db: Database):
        proj = db.create_project("fcontext")
        counts = db.delete_project(proj["id"])
        assert counts is not None
        assert db.get_project("fcontext") is None


class TestGoals:
    def test_add_goal(self, db: Database):
        db.create_project("fcontext")
        goal = db.add_goal("fcontext", "让所有人了解fcontext")
        assert goal["title"] == "让所有人了解fcontext"
        assert goal["status"] == "active"
        assert goal["id"].startswith("goal-")

    def test_add_goal_project_not_found(self, db: Database):
        with pytest.raises(ValueError, match="Project not found"):
            db.add_goal("nonexistent", "some goal")

    def test_list_goals(self, db: Database):
        db.create_project("fcontext")
        db.add_goal("fcontext", "Goal A")
        db.add_goal("fcontext", "Goal B")
        goals = db.list_goals("fcontext")
        assert len(goals) == 2

    def test_list_goals_empty_project(self, db: Database):
        assert db.list_goals("nonexistent") == []

    def test_update_goal_status(self, db: Database):
        db.create_project("fcontext")
        goal = db.add_goal("fcontext", "Goal A")
        result = db.update_goal(goal["id"], "status", "achieved")
        assert result["status"] == "achieved"

    def test_update_goal_invalid_field(self, db: Database):
        db.create_project("fcontext")
        goal = db.add_goal("fcontext", "Goal A")
        assert db.update_goal(goal["id"], "invalid", "val") is None

    def test_multiple_goals_per_project(self, db: Database):
        db.create_project("fcontext")
        db.add_goal("fcontext", "让开发者知道fcontext")
        db.add_goal("fcontext", "获取1000 GitHub stars")
        db.add_goal("fcontext", "让AI工具链默认集成fcontext")
        goals = db.list_goals("fcontext")
        assert len(goals) == 3


class TestPlatforms:
    def test_add_platform(self, db: Database):
        db.create_project("fcontext")
        plat = db.add_platform("fcontext", "twitter", directions="build-in-public", pace="3/周")
        assert plat["name"] == "twitter"
        assert plat["directions"] == "build-in-public"
        assert plat["pace"] == "3/周"

    def test_add_platform_project_not_found(self, db: Database):
        with pytest.raises(ValueError, match="Project not found"):
            db.add_platform("nonexistent", "twitter")

    def test_add_duplicate_platform_fails(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        with pytest.raises(Exception):
            db.add_platform("fcontext", "twitter")

    def test_list_platforms(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        db.add_platform("fcontext", "devto")
        platforms = db.list_platforms("fcontext")
        assert len(platforms) == 2

    def test_get_platform(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter", directions="bip")
        plat = db.get_platform("fcontext", "twitter")
        assert plat is not None
        assert plat["directions"] == "bip"

    def test_get_platform_not_found(self, db: Database):
        db.create_project("fcontext")
        assert db.get_platform("fcontext", "nonexistent") is None

    def test_update_platform(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        result = db.update_platform("fcontext", "twitter", "pace", "5/周")
        assert result["pace"] == "5/周"

    def test_update_platform_invalid_field(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        assert db.update_platform("fcontext", "twitter", "invalid", "val") is None

    def test_list_platforms_project_not_found(self, db: Database):
        assert db.list_platforms("nonexistent") == []

    def test_get_platform_project_not_found(self, db: Database):
        assert db.get_platform("nonexistent", "twitter") is None


class TestPlans:
    def test_create_plan(self, db: Database):
        db.create_project("fcontext")
        plan = db.create_plan("fcontext", "cold-start", strategy="英文社区渗透")
        assert plan["name"] == "cold-start"
        assert plan["strategy"] == "英文社区渗透"
        assert plan["status"] == "active"

    def test_create_plan_with_goal(self, db: Database):
        db.create_project("fcontext")
        goal = db.add_goal("fcontext", "Goal A")
        plan = db.create_plan("fcontext", "cold-start", goal_id=goal["id"])
        assert plan["goal_id"] == goal["id"]

    def test_create_plan_project_not_found(self, db: Database):
        with pytest.raises(ValueError, match="Project not found"):
            db.create_plan("nonexistent", "plan-a")

    def test_create_duplicate_plan_fails(self, db: Database):
        db.create_project("fcontext")
        db.create_plan("fcontext", "cold-start")
        with pytest.raises(Exception):
            db.create_plan("fcontext", "cold-start")

    def test_list_plans(self, db: Database):
        db.create_project("fcontext")
        db.create_plan("fcontext", "plan-a")
        db.create_plan("fcontext", "plan-b")
        plans = db.list_plans("fcontext")
        assert len(plans) == 2

    def test_list_plans_filter_status(self, db: Database):
        db.create_project("fcontext")
        db.create_plan("fcontext", "plan-a")
        db.create_plan("fcontext", "plan-b")
        db.update_plan("fcontext", "plan-b", "status", "completed")
        active = db.list_plans("fcontext", status="active")
        assert len(active) == 1

    def test_get_plan(self, db: Database):
        db.create_project("fcontext")
        db.create_plan("fcontext", "cold-start")
        plan = db.get_plan("fcontext", "cold-start")
        assert plan is not None
        assert plan["name"] == "cold-start"

    def test_update_plan(self, db: Database):
        db.create_project("fcontext")
        db.create_plan("fcontext", "cold-start")
        result = db.update_plan("fcontext", "cold-start", "strategy", "New strategy")
        assert result["strategy"] == "New strategy"

    def test_assign_plan_platform(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        db.create_plan("fcontext", "cold-start")
        result = db.assign_plan_platform("fcontext", "cold-start", "twitter", direction="bip", target=12)
        assert result is not None
        assert result["target_count"] == 12

    def test_assign_plan_platform_not_found(self, db: Database):
        db.create_project("fcontext")
        db.create_plan("fcontext", "cold-start")
        assert db.assign_plan_platform("fcontext", "cold-start", "nonexistent") is None

    def test_list_plan_platforms(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        db.add_platform("fcontext", "devto")
        db.create_plan("fcontext", "cold-start")
        db.assign_plan_platform("fcontext", "cold-start", "twitter", direction="bip", target=12)
        db.assign_plan_platform("fcontext", "cold-start", "devto", direction="arch", target=3)
        result = db.list_plan_platforms("fcontext", "cold-start")
        assert len(result) == 2
        names = [r["platform_name"] for r in result]
        assert "twitter" in names
        assert "devto" in names

    def test_list_plans_project_not_found(self, db: Database):
        assert db.list_plans("nonexistent") == []

    def test_get_plan_project_not_found(self, db: Database):
        assert db.get_plan("nonexistent", "plan") is None

    def test_get_plan_plan_not_found(self, db: Database):
        db.create_project("fcontext")
        assert db.get_plan("fcontext", "nonexistent") is None

    def test_update_plan_invalid_field(self, db: Database):
        db.create_project("fcontext")
        db.create_plan("fcontext", "cold-start")
        assert db.update_plan("fcontext", "cold-start", "invalid_field", "val") is None

    def test_list_plan_platforms_not_found(self, db: Database):
        db.create_project("fcontext")
        assert db.list_plan_platforms("fcontext", "nonexistent") == []


class TestContents:
    def test_register_content(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        content = db.register_content(
            title="My first tweet",
            project_name="fcontext",
            platform_name="twitter",
            direction="build-in-public",
            content_type="thread",
        )
        assert content["title"] == "My first tweet"
        assert content["content_type"] == "thread"
        assert content["status"] == "draft"
        assert content["id"].startswith("cont-")

    def test_register_content_with_source_path(self, db: Database, sample_workspace: Path):
        content = db.register_content(
            source_path=str(sample_workspace / "hello-world.md"),
            title="Hello World",
        )
        assert content["source_path"].endswith("hello-world.md")

    def test_list_contents_all(self, db: Database):
        db.create_project("fcontext")
        db.register_content(title="A", project_name="fcontext")
        db.register_content(title="B", project_name="fcontext")
        contents = db.list_contents()
        assert len(contents) == 2

    def test_list_contents_filter_project(self, db: Database):
        db.create_project("fcontext")
        db.create_project("fgeo")
        db.register_content(title="A", project_name="fcontext")
        db.register_content(title="B", project_name="fgeo")
        contents = db.list_contents(project_name="fcontext")
        assert len(contents) == 1
        assert contents[0]["title"] == "A"

    def test_list_contents_filter_status(self, db: Database):
        db.create_project("fcontext")
        db.register_content(title="A", project_name="fcontext", status="draft")
        db.register_content(title="B", project_name="fcontext", status="published")
        drafts = db.list_contents(status="draft")
        assert len(drafts) == 1
        assert drafts[0]["title"] == "A"

    def test_list_contents_filter_platform(self, db: Database):
        db.create_project("fcontext")
        db.add_platform("fcontext", "twitter")
        db.add_platform("fcontext", "devto")
        db.register_content(title="A", project_name="fcontext", platform_name="twitter")
        db.register_content(title="B", project_name="fcontext", platform_name="devto")
        twitter_content = db.list_contents(project_name="fcontext", platform_name="twitter")
        assert len(twitter_content) == 1
        assert twitter_content[0]["title"] == "A"

    def test_list_contents_filter_direction(self, db: Database):
        db.create_project("fcontext")
        db.register_content(title="A", project_name="fcontext", direction="bip")
        db.register_content(title="B", project_name="fcontext", direction="arch")
        bip = db.list_contents(direction="bip")
        assert len(bip) == 1

    def test_get_content(self, db: Database):
        db.create_project("fcontext")
        created = db.register_content(title="Test", project_name="fcontext")
        content = db.get_content(created["id"])
        assert content is not None
        assert content["title"] == "Test"

    def test_get_content_not_found(self, db: Database):
        assert db.get_content("nonexistent") is None

    def test_update_content(self, db: Database):
        db.create_project("fcontext")
        created = db.register_content(title="Test", project_name="fcontext")
        result = db.update_content(created["id"], "status", "published")
        assert result["status"] == "published"

    def test_update_content_invalid_field(self, db: Database):
        db.create_project("fcontext")
        created = db.register_content(title="Test", project_name="fcontext")
        assert db.update_content(created["id"], "invalid", "val") is None

    def test_remove_content(self, db: Database):
        db.create_project("fcontext")
        created = db.register_content(title="Test", project_name="fcontext")
        assert db.remove_content(created["id"]) is True
        assert db.get_content(created["id"]) is None

    def test_remove_content_not_found(self, db: Database):
        assert db.remove_content("nonexistent") is False

    def test_update_content_not_found(self, db: Database):
        assert db.update_content("nonexistent", "status", "published") is None


class TestProjectStatus:
    def test_project_status(self, seeded_db: Database):
        status = seeded_db.project_status("fcontext")
        assert status is not None
        assert status["project"]["name"] == "fcontext"
        assert len(status["goals"]) == 1
        assert len(status["plans"]) == 1
        assert len(status["platforms"]) == 2

    def test_project_status_platform_stats(self, seeded_db: Database):
        status = seeded_db.project_status("fcontext")
        twitter_stats = [p for p in status["platforms"] if p["name"] == "twitter"][0]
        assert twitter_stats["published"] == 1
        assert twitter_stats["total"] == 1

    def test_project_status_plan_progress(self, seeded_db: Database):
        status = seeded_db.project_status("fcontext")
        plan = status["plans"][0]
        assert plan["name"] == "cold-start"
        assert len(plan["assignments"]) == 2
        twitter_assign = [a for a in plan["assignments"] if a["platform"] == "twitter"][0]
        assert twitter_assign["target"] == 12
        assert twitter_assign["done"] == 1

    def test_project_status_not_found(self, db: Database):
        assert db.project_status("nonexistent") is None


class TestHelpers:
    def test_make_id_deterministic(self):
        a = _make_id("proj", "fcontext")
        b = _make_id("proj", "fcontext")
        assert a == b

    def test_make_id_prefix(self):
        assert _make_id("proj", "test").startswith("proj-")
        assert _make_id("goal", "test").startswith("goal-")

    def test_detect_workspace(self, sample_workspace: Path):
        result = Database._detect_workspace(sample_workspace / "hello-world.md")
        assert result == sample_workspace

    def test_detect_workspace_not_found(self, tmp_path: Path):
        f = tmp_path / "orphan.md"
        f.write_text("test")
        assert Database._detect_workspace(f) is None


class TestBrand:
    def test_get_brand_empty(self, db: Database):
        brand = db.get_brand()
        assert brand["name"] == ""
        assert brand["positioning"] == ""
        assert brand["voice"] == ""
        assert brand["core_values"] == ""
        assert brand["topics"] == ""

    def test_set_brand_creates_singleton(self, db: Database):
        result = db.set_brand("name", "Marvin Ma")
        assert result is not None
        assert result["name"] == "Marvin Ma"

    def test_set_brand_updates_field(self, db: Database):
        db.set_brand("name", "Marvin Ma")
        db.set_brand("positioning", "AI工具布道者")
        brand = db.get_brand()
        assert brand["name"] == "Marvin Ma"
        assert brand["positioning"] == "AI工具布道者"

    def test_set_brand_idempotent(self, db: Database):
        db.set_brand("name", "Marvin Ma")
        db.set_brand("name", "MarvinTalk")
        brand = db.get_brand()
        assert brand["name"] == "MarvinTalk"
        # Only one singleton row exists
        count = db.conn.execute("SELECT COUNT(*) FROM brand").fetchone()[0]
        assert count == 1

    def test_set_brand_invalid_field(self, db: Database):
        result = db.set_brand("nonexistent", "value")
        assert result is None

    def test_set_brand_all_fields(self, db: Database):
        fields = {"name": "Marvin", "positioning": "P", "voice": "V", "core_values": "Va", "topics": "T"}
        for k, v in fields.items():
            db.set_brand(k, v)
        brand = db.get_brand()
        for k, v in fields.items():
            assert brand[k] == v


class TestStyles:
    def test_add_style(self, db: Database):
        style = db.add_style("twitter", desc="Build-in-public", formula="hook→insight→CTA")
        assert style["platform"] == "twitter"
        assert style["desc"] == "Build-in-public"
        assert style["formula"] == "hook→insight→CTA"

    def test_add_style_duplicate_raises(self, db: Database):
        db.add_style("twitter")
        with pytest.raises(ValueError, match="already exists"):
            db.add_style("twitter")

    def test_add_style_alias_x(self, db: Database):
        style = db.add_style("x", desc="Twitter via alias")
        assert style["platform"] == "twitter"

    def test_add_style_alias_wechat(self, db: Database):
        style = db.add_style("wechat")
        assert style["platform"] == "公众号"

    def test_add_style_alias_bilibili(self, db: Database):
        style = db.add_style("bilibili")
        assert style["platform"] == "B站"

    def test_get_style(self, db: Database):
        db.add_style("devto", desc="Developer audience", formula="problem→solution→code")
        style = db.get_style("devto")
        assert style is not None
        assert style["desc"] == "Developer audience"

    def test_get_style_not_found(self, db: Database):
        assert db.get_style("nonexistent") is None

    def test_get_style_via_alias(self, db: Database):
        db.add_style("公众号")
        style = db.get_style("wechat")
        assert style is not None
        assert style["platform"] == "公众号"

    def test_list_styles(self, db: Database):
        db.add_style("twitter")
        db.add_style("devto")
        db.add_style("medium")
        styles = db.list_styles()
        assert len(styles) == 3
        platforms = [s["platform"] for s in styles]
        assert "twitter" in platforms
        assert "devto" in platforms
        assert "medium" in platforms

    def test_list_styles_empty(self, db: Database):
        assert db.list_styles() == []

    def test_update_style(self, db: Database):
        db.add_style("twitter", tone="casual")
        result = db.update_style("twitter", "tone", "punchy and direct")
        assert result is not None
        assert result["tone"] == "punchy and direct"

    def test_update_style_invalid_field(self, db: Database):
        db.add_style("twitter")
        assert db.update_style("twitter", "nonexistent", "value") is None

    def test_update_style_not_found(self, db: Database):
        assert db.update_style("nonexistent", "desc", "value") is None

    def test_update_style_via_alias(self, db: Database):
        db.add_style("twitter")
        result = db.update_style("x", "formula", "hook→CTA")
        assert result is not None
        assert result["formula"] == "hook→CTA"

    def test_schema_includes_brand_style_tables(self, db: Database):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "brand" in names
        assert "styles" in names

    def test_schema_includes_publish_tasks_table(self, db: Database):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "publish_tasks" in names

    def test_platforms_has_publish_url_column(self, db: Database):
        cols = [row[1] for row in db.conn.execute("PRAGMA table_info(platforms)").fetchall()]
        assert "publish_url" in cols

    def test_migration_adds_publish_url_to_old_schema(self, db: Database):
        """Simulate upgrading from 0.3.0: drop publish_url column, re-run init_schema."""
        # SQLite doesn't support DROP COLUMN before 3.35; recreate table without publish_url
        db.conn.executescript("""
            CREATE TABLE platforms_old AS SELECT id, project_id, name, directions, pace,
                status, last_published_at, created_at, updated_at FROM platforms;
            DROP TABLE platforms;
            ALTER TABLE platforms_old RENAME TO platforms;
        """)
        # Verify column is gone
        cols_before = {row[1] for row in db.conn.execute("PRAGMA table_info(platforms)").fetchall()}
        assert "publish_url" not in cols_before
        # Re-run migration
        db.init_schema()
        cols_after = {row[1] for row in db.conn.execute("PRAGMA table_info(platforms)").fetchall()}
        assert "publish_url" in cols_after


class TestPublishTasks:
    """Tests for publish_task CRUD in Database."""

    def _setup(self, db: Database):
        """Create project + platform + content, return content_id."""
        db.create_project("proj")
        db.add_platform("proj", "blog")
        content = db.register_content(title="Test Post", project_name="proj", platform_name="blog")
        return content["id"]

    def test_create_and_get_publish_task(self, db: Database):
        content_id = self._setup(db)
        task = db.create_publish_task(
            task_id="ptask-abc12345",
            content_id=content_id,
            repo_url="https://github.com/u/blog.git",
            branch="fgeo/test",
            task_dir="/tmp/test",
            pr_url="https://github.com/u/blog/pull/1",
        )
        assert task["id"] == "ptask-abc12345"
        assert task["status"] == "pr_open"
        assert task["pr_url"] == "https://github.com/u/blog/pull/1"

        fetched = db.get_publish_task("ptask-abc12345")
        assert fetched is not None
        assert fetched["branch"] == "fgeo/test"

    def test_get_publish_task_not_found(self, db: Database):
        assert db.get_publish_task("ptask-nope") is None

    def test_list_publish_tasks_empty(self, db: Database):
        assert db.list_publish_tasks() == []

    def test_list_publish_tasks_filter_status(self, db: Database):
        content_id = self._setup(db)
        db.create_publish_task("ptask-00000001", content_id, status="pr_open")
        db.create_publish_task("ptask-00000002", content_id, status="merged")
        pr_open = db.list_publish_tasks(status="pr_open")
        assert len(pr_open) == 1
        assert pr_open[0]["id"] == "ptask-00000001"

    def test_list_publish_tasks_filter_content_id(self, db: Database):
        """Covers the content_id filter branch (DB lines 745-746)."""
        content_id = self._setup(db)
        db.create_publish_task("ptask-00000003", content_id)
        result = db.list_publish_tasks(content_id=content_id)
        assert len(result) == 1
        assert result[0]["id"] == "ptask-00000003"

        # Filter by a different content_id returns nothing
        empty = db.list_publish_tasks(content_id="cont-doesnotexist")
        assert empty == []

    def test_update_publish_task(self, db: Database):
        content_id = self._setup(db)
        db.create_publish_task("ptask-00000004", content_id)
        result = db.update_publish_task("ptask-00000004", "status", "merged")
        assert result is not None
        assert result["status"] == "merged"

    def test_update_publish_task_invalid_field(self, db: Database):
        """Covers early-return when field not in allowed (DB line 755)."""
        content_id = self._setup(db)
        db.create_publish_task("ptask-00000005", content_id)
        result = db.update_publish_task("ptask-00000005", "nonexistent_field", "val")
        assert result is None

    def test_update_publish_task_not_found(self, db: Database):
        """Covers early-return when task doesn't exist (DB line 758)."""
        result = db.update_publish_task("ptask-nope", "status", "merged")
        assert result is None
