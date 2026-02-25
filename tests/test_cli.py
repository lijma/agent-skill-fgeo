"""Tests for fgeo CLI commands — project, goal, platform, plan, content, status."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fgeo.cli import app

runner = CliRunner()


def _extract_id(output: str, prefix: str = "cont") -> str:
    """Parse an ID like 'cont-a1b2c3d4' from CLI output."""
    match = re.search(rf"({prefix}-[0-9a-f]+)", output)
    assert match, f"Could not find {prefix}-* ID in output:\n{output}"
    return match.group(1)


class TestVersion:
    def test_version(self, fgeo_home: Path):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output

    def test_help(self, fgeo_home: Path):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "project" in result.output
        assert "goal" in result.output
        assert "platform" in result.output
        assert "plan" in result.output
        assert "content" in result.output
        assert "status" in result.output


class TestProjectCommands:
    def test_project_create(self, fgeo_home: Path):
        result = runner.invoke(app, ["project", "create", "fcontext", "--desc", "AI context manager"])
        assert result.exit_code == 0
        assert "Project created" in result.output
        assert "fcontext" in result.output

    def test_project_create_duplicate(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["project", "create", "fcontext"])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_project_list(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "proj-a"])
        runner.invoke(app, ["project", "create", "proj-b"])
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0
        assert "proj-a" in result.output
        assert "proj-b" in result.output

    def test_project_list_empty(self, fgeo_home: Path):
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0
        assert "No projects" in result.output

    def test_project_show(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext", "--desc", "AI context"])
        result = runner.invoke(app, ["project", "show", "fcontext"])
        assert result.exit_code == 0
        assert "fcontext" in result.output
        assert "AI context" in result.output

    def test_project_show_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["project", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_project_set(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["project", "set", "fcontext", "description", "Updated desc"])
        assert result.exit_code == 0
        assert "Updated desc" in result.output

    def test_project_remove_force(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["goal", "add", "fcontext", "Goal A"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter", "--directions", "bip"])
        result = runner.invoke(app, ["project", "remove", "fcontext", "--force"])
        assert result.exit_code == 0
        assert "Removed project" in result.output
        assert "fcontext" in result.output
        assert "1 goals" in result.output
        assert "1 platforms" in result.output
        # Verify gone
        list_result = runner.invoke(app, ["project", "list"])
        assert "No projects" in list_result.output

    def test_project_remove_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["project", "remove", "nonexistent", "--force"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_project_remove_confirm_yes(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["project", "remove", "fcontext"], input="y\n")
        assert result.exit_code == 0
        assert "Removed project" in result.output

    def test_project_remove_confirm_no(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["project", "remove", "fcontext"], input="n\n")
        assert result.exit_code != 0  # typer.Abort
        # Project still exists
        list_result = runner.invoke(app, ["project", "list"])
        assert "fcontext" in list_result.output

    def test_project_remove_empty_cleanup(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["project", "remove", "fcontext", "--force"])
        assert result.exit_code == 0
        assert "Removed project" in result.output
        # No "Cleaned up" line when all counts are 0
        assert "Cleaned up" not in result.output


class TestGoalCommands:
    def test_goal_add(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["goal", "add", "fcontext", "让所有人了解fcontext"])
        assert result.exit_code == 0
        assert "Goal added" in result.output

    def test_goal_add_project_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["goal", "add", "nonexistent", "goal"])
        assert result.exit_code == 1

    def test_goal_list(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["goal", "add", "fcontext", "Goal A"])
        runner.invoke(app, ["goal", "add", "fcontext", "Goal B"])
        result = runner.invoke(app, ["goal", "list", "fcontext"])
        assert result.exit_code == 0
        assert "Goal A" in result.output
        assert "Goal B" in result.output

    def test_goal_list_empty(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["goal", "list", "fcontext"])
        assert result.exit_code == 0
        assert "No goals" in result.output

    def test_goal_set_status(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        add_result = runner.invoke(app, ["goal", "add", "fcontext", "Goal A"])
        goal_id = _extract_id(add_result.output, "goal")
        result = runner.invoke(app, ["goal", "set", goal_id, "status", "achieved"])
        assert result.exit_code == 0
        assert "achieved" in result.output


class TestPlatformCommands:
    def test_platform_add(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, [
            "platform", "add", "fcontext", "twitter",
            "--directions", "build-in-public,hot-takes",
            "--pace", "3/周",
        ])
        assert result.exit_code == 0
        assert "Platform added" in result.output
        assert "twitter" in result.output

    def test_platform_add_project_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["platform", "add", "nonexistent", "twitter"])
        assert result.exit_code == 1

    def test_platform_add_duplicate(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter"])
        result = runner.invoke(app, ["platform", "add", "fcontext", "twitter"])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_platform_list(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter"])
        runner.invoke(app, ["platform", "add", "fcontext", "devto"])
        result = runner.invoke(app, ["platform", "list", "fcontext"])
        assert result.exit_code == 0
        assert "twitter" in result.output
        assert "devto" in result.output

    def test_platform_show(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter", "--directions", "bip"])
        result = runner.invoke(app, ["platform", "show", "fcontext", "twitter"])
        assert result.exit_code == 0
        assert "twitter" in result.output
        assert "bip" in result.output

    def test_platform_set(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter"])
        result = runner.invoke(app, ["platform", "set", "fcontext", "twitter", "pace", "5/周"])
        assert result.exit_code == 0
        assert "5/周" in result.output


class TestPlanCommands:
    def test_plan_create(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, [
            "plan", "create", "fcontext", "cold-start",
            "--strategy", "英文社区渗透",
        ])
        assert result.exit_code == 0
        assert "Plan created" in result.output
        assert "cold-start" in result.output

    def test_plan_create_project_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["plan", "create", "nonexistent", "plan-a"])
        assert result.exit_code == 1

    def test_plan_create_duplicate(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["plan", "create", "fcontext", "cold-start"])
        result = runner.invoke(app, ["plan", "create", "fcontext", "cold-start"])
        assert result.exit_code == 1

    def test_plan_list(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["plan", "create", "fcontext", "plan-a"])
        runner.invoke(app, ["plan", "create", "fcontext", "plan-b"])
        result = runner.invoke(app, ["plan", "list", "fcontext"])
        assert result.exit_code == 0
        assert "plan-a" in result.output
        assert "plan-b" in result.output

    def test_plan_show(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["plan", "create", "fcontext", "cold-start", "--strategy", "Test"])
        result = runner.invoke(app, ["plan", "show", "fcontext", "cold-start"])
        assert result.exit_code == 0
        assert "cold-start" in result.output

    def test_plan_assign(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter"])
        runner.invoke(app, ["plan", "create", "fcontext", "cold-start"])
        result = runner.invoke(app, [
            "plan", "assign", "fcontext", "cold-start", "twitter",
            "--direction", "bip", "--target", "12",
        ])
        assert result.exit_code == 0
        assert "Assigned" in result.output

    def test_plan_set(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["plan", "create", "fcontext", "cold-start"])
        result = runner.invoke(app, ["plan", "set", "fcontext", "cold-start", "status", "completed"])
        assert result.exit_code == 0
        assert "completed" in result.output


class TestContentCommands:
    def test_content_register_file(self, fgeo_home: Path, sample_workspace: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "devto"])
        result = runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
            "--project", "fcontext",
            "--platform", "devto",
            "--direction", "tutorial",
        ])
        assert result.exit_code == 0
        assert "Content registered" in result.output
        assert "Hello World" in result.output

    def test_content_register_nonexistent(self, fgeo_home: Path):
        result = runner.invoke(app, ["content", "register", "/nonexistent/file.md"])
        assert result.exit_code == 1

    def test_content_register_video(self, fgeo_home: Path, sample_workspace: Path):
        result = runner.invoke(app, [
            "content", "register", str(sample_workspace / "demo.mp4"),
            "--title", "Demo Video",
        ])
        assert result.exit_code == 0
        assert "video" in result.output.lower() or "Demo Video" in result.output

    def test_content_list(self, fgeo_home: Path, sample_workspace: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
            "--project", "fcontext",
        ])
        result = runner.invoke(app, ["content", "list"])
        assert result.exit_code == 0
        assert "cont-" in result.output
        assert "1 items" in result.output

    def test_content_list_empty(self, fgeo_home: Path):
        result = runner.invoke(app, ["content", "list"])
        assert result.exit_code == 0
        assert "No content" in result.output

    def test_content_list_filter_project(self, fgeo_home: Path, sample_workspace: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["project", "create", "fgeo"])
        runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
            "--project", "fcontext",
        ])
        runner.invoke(app, [
            "content", "register", str(sample_workspace / "bare-article.md"),
            "--project", "fgeo",
        ])
        result = runner.invoke(app, ["content", "list", "--project", "fcontext"])
        assert result.exit_code == 0
        assert "1 items" in result.output

    def test_content_show(self, fgeo_home: Path, sample_workspace: Path):
        reg = runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
        ])
        cid = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["content", "show", cid])
        assert result.exit_code == 0
        assert "Hello World" in result.output

    def test_content_show_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["content", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_content_set(self, fgeo_home: Path, sample_workspace: Path):
        reg = runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
        ])
        cid = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["content", "set", cid, "status", "published"])
        assert result.exit_code == 0
        assert "published" in result.output

    def test_content_remove(self, fgeo_home: Path, sample_workspace: Path):
        reg = runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
        ])
        cid = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["content", "remove", cid, "--force"])
        assert result.exit_code == 0
        assert "Removed" in result.output


class TestStatusCommand:
    def _seed_project(self, fgeo_home: Path):
        """Seed a full project via CLI commands."""
        runner.invoke(app, ["project", "create", "fcontext", "--desc", "AI context manager"])
        runner.invoke(app, ["goal", "add", "fcontext", "让所有人了解fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter", "--directions", "bip", "--pace", "3/周"])
        runner.invoke(app, ["platform", "add", "fcontext", "devto", "--directions", "arch", "--pace", "2/月"])
        runner.invoke(app, ["plan", "create", "fcontext", "cold-start", "--strategy", "英文社区渗透"])
        runner.invoke(app, ["plan", "assign", "fcontext", "cold-start", "twitter", "--direction", "bip", "--target", "12"])

    def test_status_basic(self, fgeo_home: Path):
        self._seed_project(fgeo_home)
        result = runner.invoke(app, ["status", "fcontext"])
        assert result.exit_code == 0
        assert "fcontext" in result.output
        assert "Goals" in result.output or "让所有人了解" in result.output

    def test_status_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["status", "nonexistent"])
        assert result.exit_code == 1

    def test_status_with_platform_filter(self, fgeo_home: Path):
        self._seed_project(fgeo_home)
        result = runner.invoke(app, ["status", "fcontext", "--platform", "twitter"])
        assert result.exit_code == 0
        assert "twitter" in result.output

    def test_status_platform_not_found(self, fgeo_home: Path):
        self._seed_project(fgeo_home)
        result = runner.invoke(app, ["status", "fcontext", "--platform", "nonexistent"])
        assert result.exit_code == 1


class TestInitCommand:
    def test_init(self, fgeo_home: Path, monkeypatch: pytest.MonkeyPatch):
        # Remove the fgeo_home to simulate fresh install
        import shutil
        shutil.rmtree(fgeo_home)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "initialized" in result.output
        assert (fgeo_home / "fgeo.db").exists() or "Database" in result.output or "created" in result.output

    def test_init_already_exists_abort(self, fgeo_home: Path):
        # fgeo_home alread exists → prompt → user says "n"
        result = runner.invoke(app, ["init"], input="n\n")
        assert result.exit_code != 0 or "Aborted" in result.output or result.exit_code == 1

    def test_init_already_exists_confirm(self, fgeo_home: Path):
        # fgeo_home already exists → prompt → user says "y" → reinitializes
        result = runner.invoke(app, ["init"], input="y\n")
        assert result.exit_code == 0
        assert "initialized" in result.output


class TestConfigFunctions:
    def test_load_config_no_file(self, fgeo_home: Path):
        from fgeo.config import load_config
        config = load_config()
        assert "version" in config

    def test_save_and_load_config(self, fgeo_home: Path):
        from fgeo.config import save_config, load_config
        save_config({"version": "test", "skills": ["copilot"]})
        loaded = load_config()
        assert loaded["version"] == "test"
        assert "copilot" in loaded["skills"]

    def test_load_config_existing_file(self, fgeo_home: Path):
        from fgeo.config import save_config, load_config
        save_config({"version": "0.2.0", "ip": {"name": "MarvinTalk"}, "skills": []})
        cfg = load_config()
        assert cfg["ip"]["name"] == "MarvinTalk"


class TestEnableCommand:
    def test_enable_list(self, fgeo_home: Path):
        result = runner.invoke(app, ["enable", "list"])
        assert result.exit_code == 0
        assert "copilot" in result.output

    def test_enable_unknown_agent(self, fgeo_home: Path):
        result = runner.invoke(app, ["enable", "unknown-agent"])
        assert result.exit_code == 1
        assert "Unknown agent" in result.output

    def test_enable_fcontext_not_installed(self, fgeo_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr("fgeo.commands.enable.shutil.which", lambda _cmd: None)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["enable", "copilot"])
        assert result.exit_code == 1
        assert "fcontext" in result.output.lower()

    def test_enable_with_fcontext_initialized(
        self, fgeo_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        (tmp_path / ".fcontext").mkdir()
        monkeypatch.setattr("fgeo.commands.enable.shutil.which", lambda _cmd: "/usr/bin/fcontext")
        from unittest.mock import MagicMock
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        monkeypatch.setattr("fgeo.commands.enable.subprocess.run", lambda *a, **kw: mock_proc)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["enable", "copilot"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    def test_enable_fcontext_not_initialized(
        self, fgeo_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        # No .fcontext dir → init is called first
        monkeypatch.setattr("fgeo.commands.enable.shutil.which", lambda _cmd: "/usr/bin/fcontext")
        from unittest.mock import MagicMock
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        monkeypatch.setattr("fgeo.commands.enable.subprocess.run", lambda *a, **kw: mock_proc)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["enable", "copilot"])
        assert result.exit_code == 0

    def test_enable_fcontext_init_fails(
        self, fgeo_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        # No .fcontext dir and init fails
        monkeypatch.setattr("fgeo.commands.enable.shutil.which", lambda _cmd: "/usr/bin/fcontext")
        from unittest.mock import MagicMock
        fail_proc = MagicMock()
        fail_proc.returncode = 1
        monkeypatch.setattr("fgeo.commands.enable.subprocess.run", lambda *a, **kw: fail_proc)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["enable", "copilot"])
        assert result.exit_code == 1

    def test_enable_agent_returns_nonzero(
        self, fgeo_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """enable step returns non-zero → warning printed (L125), but overall success."""
        (tmp_path / ".fcontext").mkdir()
        monkeypatch.setattr("fgeo.commands.enable.shutil.which", lambda _cmd: "/usr/bin/fcontext")
        from unittest.mock import MagicMock
        fail_proc = MagicMock()
        fail_proc.returncode = 1
        monkeypatch.setattr("fgeo.commands.enable.subprocess.run", lambda *a, **kw: fail_proc)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["enable", "copilot"])
        assert result.exit_code == 0
        assert "non-zero" in result.output


class TestEnableHelpers:
    """Test enable helper functions directly to cover exception branches."""

    def test_init_fcontext_exception(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        from fgeo.commands.enable import _init_fcontext

        def raise_err(*a, **kw):
            raise FileNotFoundError("fcontext not found")

        monkeypatch.setattr("fgeo.commands.enable.subprocess.run", raise_err)
        assert _init_fcontext(tmp_path) is False

    def test_enable_fcontext_agent_exception(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        from fgeo.commands.enable import _enable_fcontext_agent

        def raise_err(*a, **kw):
            raise FileNotFoundError("fcontext not found")

        monkeypatch.setattr("fgeo.commands.enable.subprocess.run", raise_err)
        assert _enable_fcontext_agent("copilot", tmp_path) is False


class TestMainModule:
    def test_main_module_import(self):
        """Importing __main__ covers the module-level import line."""
        import importlib
        import fgeo.__main__  # noqa: F401  — covers L3 "from fgeo.cli import app"
        assert hasattr(fgeo.__main__, "app")


class TestEdgeCases:
    """Extra edge-case tests for uncovered CLI branches."""

    def test_plan_list_empty(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["plan", "list", "fcontext"])
        assert result.exit_code == 0
        assert "No plans" in result.output

    def test_plan_show_not_found(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["plan", "show", "fcontext", "nonexistent"])
        assert result.exit_code == 1

    def test_plan_assign_not_found(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["plan", "create", "fcontext", "cold-start"])
        result = runner.invoke(app, ["plan", "assign", "fcontext", "cold-start", "nonexistent"])
        assert result.exit_code == 1

    def test_plan_set_not_found(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["plan", "set", "fcontext", "nonexistent", "status", "completed"])
        assert result.exit_code == 1

    def test_platform_list_empty(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["platform", "list", "fcontext"])
        assert result.exit_code == 0
        assert "No platforms" in result.output

    def test_platform_show_not_found(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["platform", "show", "fcontext", "nonexistent"])
        assert result.exit_code == 1

    def test_platform_set_not_found(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        result = runner.invoke(app, ["platform", "set", "fcontext", "nonexistent", "pace", "5/w"])
        assert result.exit_code == 1

    def test_project_set_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["project", "set", "nonexistent", "description", "x"])
        assert result.exit_code == 1

    def test_project_show_with_goals_plans(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["goal", "add", "fcontext", "Be famous"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter"])
        runner.invoke(app, ["plan", "create", "fcontext", "launch"])
        result = runner.invoke(app, ["project", "show", "fcontext"])
        assert result.exit_code == 0
        assert "Goals" in result.output
        assert "Platforms" in result.output
        assert "Plans" in result.output

    def test_goal_set_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["goal", "set", "nonexistent", "status", "achieved"])
        assert result.exit_code == 1

    def test_content_set_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["content", "set", "nonexistent", "status", "published"])
        assert result.exit_code == 1

    def test_content_remove_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["content", "remove", "nonexistent", "--force"])
        assert result.exit_code == 1

    def test_content_register_bare_md(self, fgeo_home: Path, sample_workspace: Path):
        """Register a markdown without frontmatter — title from H1."""
        result = runner.invoke(app, [
            "content", "register", str(sample_workspace / "bare-article.md"),
        ])
        assert result.exit_code == 0
        assert "Bare Article" in result.output

    def test_content_register_slide_type(self, fgeo_home: Path, tmp_path: Path):
        """Register a .pdf file — should be auto-detected as slide and use stem as title."""
        pdf = tmp_path / "my-presentation.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = runner.invoke(app, ["content", "register", str(pdf)])
        assert result.exit_code == 0
        assert "slide" in result.output
        assert "my presentation" in result.output.lower()

    def test_content_register_video_no_title(self, fgeo_home: Path, sample_workspace: Path):
        """Register a video file without --title — title derived from filename stem."""
        result = runner.invoke(app, ["content", "register", str(sample_workspace / "demo.mp4")])
        assert result.exit_code == 0
        assert "demo" in result.output.lower()

    def test_content_register_bad_utf8_md(self, fgeo_home: Path, tmp_path: Path):
        """Register an .md file with invalid UTF-8 — triggers except in _extract_frontmatter."""
        bad_md = tmp_path / "bad-encoding.md"
        bad_md.write_bytes(b"---\ntitle: test\n---\n\xff\xfe bad bytes")
        result = runner.invoke(app, ["content", "register", str(bad_md)])
        assert result.exit_code == 0
        # title falls back to stem
        assert "bad encoding" in result.output.lower()

    def test_content_remove_interactive_confirm(self, fgeo_home: Path, sample_workspace: Path):
        """Remove without --force, confirm 'y'."""
        reg = runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
        ])
        cid = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["content", "remove", cid], input="y\n")
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_content_remove_interactive_abort(self, fgeo_home: Path, sample_workspace: Path):
        """Remove without --force, cancel with 'n'."""
        reg = runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
        ])
        cid = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["content", "remove", cid], input="n\n")
        # Content should still exist — exit via Abort
        assert result.exit_code != 0 or "Removed" not in result.output

    def test_plan_show_with_platform_assignments(self, fgeo_home: Path):
        """Plan show with assigned platforms + target_count — exercises progress bar branch."""
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "twitter"])
        runner.invoke(app, ["plan", "create", "fcontext", "launch"])
        runner.invoke(app, [
            "plan", "assign", "fcontext", "launch", "twitter",
            "--direction", "bip", "--target", "10",
        ])
        result = runner.invoke(app, ["plan", "show", "fcontext", "launch"])
        assert result.exit_code == 0
        assert "twitter" in result.output
        assert "bip" in result.output

    def test_plan_show_assignments_without_target(self, fgeo_home: Path):
        """Plan assign with target=0 — exercises the pct-without-target branch."""
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "devto"])
        runner.invoke(app, ["plan", "create", "fcontext", "launch"])
        runner.invoke(app, ["plan", "assign", "fcontext", "launch", "devto"])
        result = runner.invoke(app, ["plan", "show", "fcontext", "launch"])
        assert result.exit_code == 0
        assert "devto" in result.output

    def test_platform_show_with_content(self, fgeo_home: Path, sample_workspace: Path):
        """Platform show with content — exercises the 'if contents:' Recent branch."""
        runner.invoke(app, ["project", "create", "fcontext"])
        runner.invoke(app, ["platform", "add", "fcontext", "devto"])
        runner.invoke(app, [
            "content", "register", str(sample_workspace / "hello-world.md"),
            "--project", "fcontext", "--platform", "devto",
        ])
        result = runner.invoke(app, ["platform", "show", "fcontext", "devto"])
        assert result.exit_code == 0
        assert "Recent" in result.output
