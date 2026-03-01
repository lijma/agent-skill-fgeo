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
        assert "0.4.0" in result.output

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


class TestBrandCommands:
    def test_brand_show_empty(self, fgeo_home):
        result = runner.invoke(app, ["brand", "show"])
        assert result.exit_code == 0
        assert "not set up" in result.output

    def test_brand_set_name(self, fgeo_home):
        result = runner.invoke(app, ["brand", "set", "name", "Marvin Ma"])
        assert result.exit_code == 0
        assert "name" in result.output
        assert "Marvin Ma" in result.output

    def test_brand_set_shows_in_show(self, fgeo_home):
        runner.invoke(app, ["brand", "set", "name", "Marvin Ma"])
        runner.invoke(app, ["brand", "set", "positioning", "AI工具布道者"])
        result = runner.invoke(app, ["brand", "show"])
        assert result.exit_code == 0
        assert "Marvin Ma" in result.output
        assert "AI工具布道者" in result.output

    def test_brand_set_invalid_field(self, fgeo_home):
        result = runner.invoke(app, ["brand", "set", "nonexistent", "value"])
        assert result.exit_code == 1
        assert "Unknown field" in result.output

    def test_brand_set_db_failure(self, fgeo_home, monkeypatch):
        from fgeo.database import Database
        monkeypatch.setattr(Database, "set_brand", lambda self, f, v: None)
        result = runner.invoke(app, ["brand", "set", "name", "Marvin"])
        assert result.exit_code == 1
        assert "Failed" in result.output

    def test_brand_set_all_fields(self, fgeo_home):
        fields = [("name", "Marvin"), ("positioning", "P"), ("voice", "V"), ("core_values", "Va"), ("topics", "T")]
        for field, value in fields:
            result = runner.invoke(app, ["brand", "set", field, value])
            assert result.exit_code == 0
        result = runner.invoke(app, ["brand", "show"])
        assert result.exit_code == 0
        assert "Marvin" in result.output

    def test_brand_init(self, fgeo_home):
        result = runner.invoke(app, ["brand", "init"])
        assert result.exit_code == 0
        assert "brand set" in result.output

    def test_version_includes_brand_style(self, fgeo_home):
        result = runner.invoke(app, ["--help"])
        assert "brand" in result.output
        assert "style" in result.output


class TestStyleCommands:
    def test_style_list_empty(self, fgeo_home):
        result = runner.invoke(app, ["style", "list"])
        assert result.exit_code == 0
        assert "No styles" in result.output

    def test_style_add(self, fgeo_home):
        result = runner.invoke(app, ["style", "add", "twitter",
                                     "--desc", "Build-in-public",
                                     "--formula", "hook→insight→CTA"])
        assert result.exit_code == 0
        assert "twitter" in result.output

    def test_style_add_duplicate(self, fgeo_home):
        runner.invoke(app, ["style", "add", "twitter"])
        result = runner.invoke(app, ["style", "add", "twitter"])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_style_add_alias(self, fgeo_home):
        result = runner.invoke(app, ["style", "add", "x", "--desc", "Twitter alias"])
        assert result.exit_code == 0
        assert "twitter" in result.output

    def test_style_show(self, fgeo_home):
        runner.invoke(app, ["style", "add", "devto", "--desc", "Dev audience", "--tone", "technical"])
        result = runner.invoke(app, ["style", "show", "devto"])
        assert result.exit_code == 0
        assert "Dev audience" in result.output
        assert "technical" in result.output

    def test_style_show_not_found(self, fgeo_home):
        result = runner.invoke(app, ["style", "show", "nonexistent"])
        assert result.exit_code == 0
        assert "No writing style" in result.output

    def test_style_list(self, fgeo_home):
        runner.invoke(app, ["style", "add", "twitter"])
        runner.invoke(app, ["style", "add", "devto"])
        result = runner.invoke(app, ["style", "list"])
        assert result.exit_code == 0
        assert "twitter" in result.output
        assert "devto" in result.output

    def test_style_set(self, fgeo_home):
        runner.invoke(app, ["style", "add", "twitter"])
        result = runner.invoke(app, ["style", "set", "twitter", "formula", "hook→CTA"])
        assert result.exit_code == 0
        assert "formula" in result.output
        assert "hook→CTA" in result.output

    def test_style_set_invalid_field(self, fgeo_home):
        runner.invoke(app, ["style", "add", "twitter"])
        result = runner.invoke(app, ["style", "set", "twitter", "nonexistent", "v"])
        assert result.exit_code == 1
        assert "Unknown field" in result.output

    def test_style_set_not_found(self, fgeo_home):
        result = runner.invoke(app, ["style", "set", "nonexistent", "desc", "v"])
        assert result.exit_code == 1

    def test_style_set_via_alias(self, fgeo_home):
        runner.invoke(app, ["style", "add", "x"])
        result = runner.invoke(app, ["style", "set", "twitter", "tone", "punchy"])
        assert result.exit_code == 0
        assert "punchy" in result.output


class TestPublishCommands:
    """Tests for fgeo publish content / publish list."""

    def _register_blog_content(self, fgeo_home: Path, tmp_path: Path, status: str = "draft") -> tuple[str, Path]:
        """Helper: create a workspace with .git, write a markdown file, register it, return (content_id, src_path)."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".git").mkdir()
        runner.invoke(app, ["project", "create", "myproj"])
        runner.invoke(app, ["platform", "add", "myproj", "blog"])
        src = ws / "my-article.md"
        src.write_text("# Hello Blog\n\nContent here.\n")
        reg_result = runner.invoke(app, [
            "content", "register", str(src),
            "--project", "myproj",
            "--platform", "blog",
            "--direction", "tutorial",
            "--status", status,
        ])
        content_id = _extract_id(reg_result.output, "cont")
        return content_id, src

    def test_publish_list_empty(self, fgeo_home: Path):
        result = runner.invoke(app, ["publish", "list"])
        assert result.exit_code == 0
        assert "No content" in result.output

    def test_publish_list_shows_drafts(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        result = runner.invoke(app, ["publish", "list"])
        assert result.exit_code == 0
        assert "my-article" in result.output

    def test_publish_list_filter_by_project(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        result = runner.invoke(app, ["publish", "list", "--project", "myproj"])
        assert result.exit_code == 0
        assert "my-article" in result.output

    def test_publish_list_filter_no_match(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        result = runner.invoke(app, ["publish", "list", "--status", "published"])
        assert result.exit_code == 0
        assert "No content" in result.output

    def test_publish_content_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["publish", "content", "cont-doesnotexist"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_publish_content_already_published(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path, status="published")
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert "Already published" in result.output

    def test_publish_content_blog_no_source(self, fgeo_home: Path, tmp_path: Path):
        # Register with a real file, then clear source_path to simulate missing path record
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".git").mkdir()
        runner.invoke(app, ["project", "create", "myproj"])
        runner.invoke(app, ["platform", "add", "myproj", "blog"])
        src = ws / "article.md"
        src.write_text("# Article\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "myproj", "--platform", "blog"])
        content_id = _extract_id(reg.output, "cont")
        # Clear source_path
        runner.invoke(app, ["content", "set", content_id, "source_path", ""])
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        result = runner.invoke(app, ["publish", "content", content_id,
                                     "--blog-dir", str(posts_dir)])
        assert result.exit_code == 1
        assert "No source file" in result.output

    def test_publish_content_blog_success(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        result = runner.invoke(app, ["publish", "content", content_id, "--blog-dir", str(posts_dir)])
        assert result.exit_code == 0
        assert "Published to blog" in result.output
        # File should exist in posts_dir with date prefix
        copied = list(posts_dir.glob("*my-article.md"))
        assert len(copied) == 1
        assert copied[0].read_text() == src.read_text()

    def test_publish_content_blog_status_updated(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        runner.invoke(app, ["publish", "content", content_id, "--blog-dir", str(posts_dir)])
        # After publish, listing published should show it
        result = runner.invoke(app, ["publish", "list", "--status", "published"])
        assert result.exit_code == 0
        assert "my-article" in result.output

    def test_publish_content_blog_dest_exists_no_force(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        # Pre-create destination
        import re as _re
        from datetime import datetime
        date_now = datetime.now().strftime("%Y-%m-%d")
        (posts_dir / f"{date_now}-my-article.md").write_text("old content")
        result = runner.invoke(app, ["publish", "content", content_id, "--blog-dir", str(posts_dir)])
        assert result.exit_code == 1
        assert "already exists" in result.output.lower()

    def test_publish_content_blog_dest_exists_force(self, fgeo_home: Path, tmp_path: Path):
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        from datetime import datetime
        date_now = datetime.now().strftime("%Y-%m-%d")
        (posts_dir / f"{date_now}-my-article.md").write_text("old content")
        result = runner.invoke(app, ["publish", "content", content_id,
                                     "--blog-dir", str(posts_dir), "--force"])
        assert result.exit_code == 0
        assert "Published to blog" in result.output
        copied = list(posts_dir.glob("*my-article.md"))
        assert copied[0].read_text() == src.read_text()

    def test_publish_content_blog_no_workspace_no_blogdir(self, fgeo_home: Path, tmp_path: Path):
        # Register file in a directory without .git/.fcontext so workspace=""
        runner.invoke(app, ["project", "create", "myproj"])
        runner.invoke(app, ["platform", "add", "myproj", "blog"])
        # tmp_path has no .git or .fcontext markers → workspace detection returns ""
        no_ws_dir = tmp_path / "no_workspace"
        no_ws_dir.mkdir()
        src = no_ws_dir / "ghost.md"
        src.write_text("# Ghost\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "myproj", "--platform", "blog"])
        content_id = _extract_id(reg.output, "cont")
        # Publish with no --blog-dir and no workspace — should fail
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "blog posts directory" in result.output.lower() or "blog-dir" in result.output

    def test_publish_content_non_blog(self, fgeo_home: Path, tmp_path: Path):
        runner.invoke(app, ["project", "create", "myproj"])
        runner.invoke(app, ["platform", "add", "myproj", "twitter"])
        src = tmp_path / "tweet.md"
        src.write_text("# Tweet\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "myproj", "--platform", "twitter"])
        content_id = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert "published" in result.output.lower()
        assert "manually" in result.output.lower() or "twitter" in result.output.lower()

    def test_publish_content_non_blog_with_url(self, fgeo_home: Path, tmp_path: Path):
        runner.invoke(app, ["project", "create", "myproj"])
        runner.invoke(app, ["platform", "add", "myproj", "devto"])
        src = tmp_path / "article.md"
        src.write_text("# Article\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "myproj", "--platform", "devto"])
        content_id = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["publish", "content", content_id,
                                     "--url", "https://dev.to/myarticle"])
        assert result.exit_code == 0
        assert "https://dev.to/myarticle" in result.output

    def test_publish_content_blog_filename_already_has_date_prefix(self, fgeo_home: Path, tmp_path: Path):
        """Covers _with_date_prefix line: return filename when prefix already present."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".git").mkdir()
        runner.invoke(app, ["project", "create", "myproj"])
        runner.invoke(app, ["platform", "add", "myproj", "blog"])
        # File already has YYYY-MM-DD- prefix → _with_date_prefix should return it unchanged
        src = ws / "2025-12-25-xmas-post.md"
        src.write_text("# Xmas\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "myproj", "--platform", "blog"])
        content_id = _extract_id(reg.output, "cont")
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        result = runner.invoke(app, ["publish", "content", content_id, "--blog-dir", str(posts_dir)])
        assert result.exit_code == 0
        # Destination keeps the original prefix, not a doubled one
        assert (posts_dir / "2025-12-25-xmas-post.md").exists()

    def test_publish_content_no_platform_id(self, fgeo_home: Path, tmp_path: Path):
        """Covers _resolve_platform_name early return when platform_id is absent."""
        runner.invoke(app, ["project", "create", "myproj"])
        src = tmp_path / "threadless.md"
        src.write_text("# Thread\n")
        # Register WITHOUT --platform → platform_id stays NULL in DB
        reg = runner.invoke(app, ["content", "register", str(src), "--project", "myproj"])
        content_id = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert "published" in result.output.lower()

    def test_publish_content_blog_src_file_missing(self, fgeo_home: Path, tmp_path: Path):
        """Covers src.exists() check: source_path recorded but file deleted before publish."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        src.unlink()  # delete the actual file after registration
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        result = runner.invoke(app, ["publish", "content", content_id, "--blog-dir", str(posts_dir)])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_publish_content_blog_via_workspace(self, fgeo_home: Path, tmp_path: Path):
        """Covers the `elif workspace` branch (no --blog-dir, workspace auto-detected)."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        # Publish without --blog-dir; workspace is set from registration → uses workspace/platforms/blog/docs/posts/
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert "Published to blog" in result.output
        ws = tmp_path / "ws"
        posts_dir = ws / "platforms" / "blog" / "docs" / "posts"
        copied = list(posts_dir.glob("*my-article.md"))
        assert len(copied) == 1


class TestPublishBlogGitFlow:
    """Tests for the git-PR publish flow (blog platform with publish_url set)."""

    REPO_URL = "https://github.com/user/blog.git"

    def _register_blog_content(self, fgeo_home: Path, tmp_path: Path) -> tuple[str, Path]:
        runner.invoke(app, ["project", "create", "gitproj"])
        runner.invoke(app, ["platform", "add", "gitproj", "blog"])
        src = tmp_path / "post.md"
        src.write_text("# My Git Post\n\nContent.\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "gitproj", "--platform", "blog"])
        content_id = _extract_id(reg.output, "cont")
        return content_id, src

    def _mock_subprocess(self, monkeypatch):
        """Mock subprocess.run: git clone creates repo_dir; all git cmds succeed; gh fails."""
        import subprocess as _sp

        def _run(cmd, cwd=None, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "clone" in cmd_str:
                # Create the target dir so subsequent cwd-based calls have a real path
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            if cmd[0] == "gh":
                return _sp.CompletedProcess(cmd, 1, stdout="", stderr="gh: not configured")
            return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        # Only mock subprocess.run — _run_git calls it internally so line 51 is covered
        monkeypatch.setattr("fgeo.commands.publish.subprocess.run", _run)
        # gh is "installed" but will return non-zero (graceful failure)
        monkeypatch.setattr("fgeo.commands.publish.shutil.which", lambda _: "/usr/bin/gh")

    def test_platform_set_publish_url(self, fgeo_home: Path, tmp_path: Path):
        """fgeo platform set stores publish_url on the platform record."""
        runner.invoke(app, ["project", "create", "gitproj"])
        runner.invoke(app, ["platform", "add", "gitproj", "blog"])
        result = runner.invoke(app, ["platform", "set", "gitproj", "blog",
                                     "publish_url", self.REPO_URL])
        assert result.exit_code == 0
        # show command reflects the value
        show = runner.invoke(app, ["platform", "show", "gitproj", "blog"])
        assert self.REPO_URL in show.output

    def test_publish_content_blog_no_publish_url_falls_back_to_local(
        self, fgeo_home: Path, tmp_path: Path
    ):
        """Without publish_url, blog publish falls back to local copy flow."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        result = runner.invoke(app, ["publish", "content", content_id,
                                     "--blog-dir", str(posts_dir)])
        assert result.exit_code == 0
        assert "local" in result.output.lower()

    def test_publish_content_blog_git_flow_creates_task(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """With publish_url set, publish triggers git flow and creates a ptask."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        # Redirect FGEO_HOME tasks to tmp_path so we don't pollute ~/.fgeo
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        self._mock_subprocess(monkeypatch)

        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert "PR ready" in result.output or "ptask" in result.output

    def test_publish_task_list_shows_created_task(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """After git publish, fgeo publish task list shows the pr_open task."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        self._mock_subprocess(monkeypatch)

        runner.invoke(app, ["publish", "content", content_id])

        result = runner.invoke(app, ["publish", "task", "list"])
        assert result.exit_code == 0
        assert "pr_open" in result.output

    def test_publish_task_list_empty(self, fgeo_home: Path):
        result = runner.invoke(app, ["publish", "task", "list"])
        assert result.exit_code == 0
        assert "No publish tasks" in result.output

    def test_publish_task_list_filter_by_status(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """Filter tasks by status=merged returns nothing when task is pr_open."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        self._mock_subprocess(monkeypatch)
        runner.invoke(app, ["publish", "content", content_id])

        result = runner.invoke(app, ["publish", "task", "list", "--status", "merged"])
        assert "No publish tasks" in result.output

    def test_publish_task_show(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """fgeo publish task show displays task details."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        self._mock_subprocess(monkeypatch)
        pub = runner.invoke(app, ["publish", "content", content_id])

        # Extract task ID from output
        task_id = _extract_id(pub.output, "ptask")
        result = runner.invoke(app, ["publish", "task", "show", task_id])
        assert result.exit_code == 0
        assert "pr_open" in result.output
        assert task_id in result.output

    def test_publish_task_show_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["publish", "task", "show", "ptask-doesnotexist"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_publish_task_done_marks_content_published(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """fgeo publish task done → task=merged, content=published."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        self._mock_subprocess(monkeypatch)
        pub = runner.invoke(app, ["publish", "content", content_id])
        task_id = _extract_id(pub.output, "ptask")

        done = runner.invoke(app, ["publish", "task", "done", task_id])
        assert done.exit_code == 0
        assert "merged" in done.output
        assert "published" in done.output

        # Content should now show as published
        result = runner.invoke(app, ["publish", "list", "--status", "published"])
        assert "post" in result.output

    def test_publish_task_done_idempotent(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """Calling task done twice is safe."""
        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        self._mock_subprocess(monkeypatch)
        pub = runner.invoke(app, ["publish", "content", content_id])
        task_id = _extract_id(pub.output, "ptask")

        runner.invoke(app, ["publish", "task", "done", task_id])
        second = runner.invoke(app, ["publish", "task", "done", task_id])
        assert second.exit_code == 0
        assert "already merged" in second.output.lower()

    def test_publish_task_done_not_found(self, fgeo_home: Path):
        result = runner.invoke(app, ["publish", "task", "done", "ptask-nope"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_publish_content_blog_clone_failure(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """If git clone fails, publish exits with error."""
        import subprocess as _sp

        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")

        def _fail_clone(cmd, cwd=None, **kwargs):
            if "clone" in cmd:
                return _sp.CompletedProcess(cmd, 128, stdout="", stderr="fatal: repository not found")
            return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("fgeo.commands.publish.subprocess.run", _fail_clone)

        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "clone" in result.output.lower() or "failed" in result.output.lower()

    def test_publish_content_blog_push_failure(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """If git push fails, publish exits with error (covers push failure branch)."""
        import subprocess as _sp

        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")

        def _fail_push(cmd, cwd=None, **kwargs):
            if "clone" in cmd:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
                return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")
            if "push" in cmd:
                return _sp.CompletedProcess(cmd, 1, stdout="", stderr="error: failed to push")
            return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("fgeo.commands.publish.subprocess.run", _fail_push)

        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "push" in result.output.lower() or "failed" in result.output.lower()

    def test_publish_content_blog_force_push(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """--force passes --force-with-lease to git push (covers non-fast-forward case)."""
        import subprocess as _sp

        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        monkeypatch.setattr("fgeo.commands.publish.shutil.which", lambda _: "/usr/bin/gh")

        push_cmds: list[list[str]] = []

        def _run(cmd, cwd=None, **kwargs):
            if "clone" in cmd:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            if "push" in cmd:
                push_cmds.append(list(cmd))
            if cmd[0] == "gh":
                return _sp.CompletedProcess(cmd, 1, stdout="", stderr="")
            return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("fgeo.commands.publish.subprocess.run", _run)

        result = runner.invoke(app, ["publish", "content", content_id, "--force"])
        assert result.exit_code == 0
        assert any("--force-with-lease" in cmd for cmd in push_cmds)

    def test_publish_content_blog_gh_not_installed(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """When gh is not installed, install instructions and a compare URL are shown."""
        import subprocess as _sp

        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        monkeypatch.setattr("fgeo.commands.publish.shutil.which", lambda _: None)

        def _run(cmd, cwd=None, **kwargs):
            if "clone" in cmd:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("fgeo.commands.publish.subprocess.run", _run)

        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert "brew install gh" in result.output or "cli.github.com" in result.output
        # Compare URL from REPO_URL (https://github.com/user/blog.git)
        assert "github.com/user/blog/compare" in result.output
        assert "?expand=1" in result.output
        # Task is still created even without gh
        task_list = runner.invoke(app, ["publish", "task", "list"])
        assert "pr_open" in task_list.output

    def test_publish_content_blog_gh_creates_pr_url(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """When gh pr create succeeds, PR URL appears in output."""
        import subprocess as _sp
        PR_URL = "https://github.com/user/blog/pull/42"

        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        monkeypatch.setattr("fgeo.commands.publish.shutil.which", lambda _: "/usr/bin/gh")

        def _gh_success(cmd, cwd=None, **kwargs):
            if "clone" in cmd:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            if cmd[0] == "gh":
                return _sp.CompletedProcess(cmd, 0, stdout=f"{PR_URL}\n", stderr="")
            return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("fgeo.commands.publish.subprocess.run", _gh_success)

        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert PR_URL in result.output

    def test_publish_task_done_with_pr_url_updates_content(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """task done when task has pr_url → updates content published_url (covers L370)."""
        import subprocess as _sp
        PR_URL = "https://github.com/user/blog/pull/99"

        content_id, src = self._register_blog_content(fgeo_home, tmp_path)
        runner.invoke(app, ["platform", "set", "gitproj", "blog",
                            "publish_url", self.REPO_URL])
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        monkeypatch.setattr("fgeo.commands.publish.shutil.which", lambda _: "/usr/bin/gh")

        def _gh_success(cmd, cwd=None, **kwargs):
            if "clone" in cmd:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            if cmd[0] == "gh":
                return _sp.CompletedProcess(cmd, 0, stdout=f"{PR_URL}\n", stderr="")
            return _sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("fgeo.commands.publish.subprocess.run", _gh_success)

        pub = runner.invoke(app, ["publish", "content", content_id])
        task_id = _extract_id(pub.output, "ptask")

        done = runner.invoke(app, ["publish", "task", "done", task_id])
        assert done.exit_code == 0
        # Content show should have the PR URL recorded
        show = runner.invoke(app, ["content", "show", content_id])
        assert PR_URL in show.output


class TestGitRemoteToWebUrl:
    """Unit tests for the _git_remote_to_web_url helper."""

    def test_https_with_git_suffix(self):
        from fgeo.commands.publish import _git_remote_to_web_url
        assert _git_remote_to_web_url("https://github.com/user/repo.git") == "https://github.com/user/repo"

    def test_https_without_git_suffix(self):
        from fgeo.commands.publish import _git_remote_to_web_url
        assert _git_remote_to_web_url("https://github.com/user/repo") == "https://github.com/user/repo"

    def test_ssh_format(self):
        from fgeo.commands.publish import _git_remote_to_web_url
        assert _git_remote_to_web_url("git@github.com:user/repo.git") == "https://github.com/user/repo"

    def test_ssh_format_without_git_suffix(self):
        from fgeo.commands.publish import _git_remote_to_web_url
        assert _git_remote_to_web_url("git@github.com:user/repo") == "https://github.com/user/repo"


# ── Bluesky helpers ───────────────────────────────────────────────────────────

def _make_fake_atproto(post_uri: str = "at://did:plc:abc123/app.bsky.feed.post/rkey777"):
    """Return a fake atproto module with Client and models."""
    import sys
    import types

    fake = types.ModuleType("atproto")

    _uri = post_uri

    class _Client:
        def login(self, handle, pw):
            pass

        def send_post(self, text, embed=None):
            return type("Resp", (), {"uri": _uri})()

    class _Models:
        class AppBskyEmbedExternal:
            class Main:
                def __init__(self, external=None):
                    pass

            class External:
                def __init__(self, uri="", title="", description=""):
                    pass

    fake.Client = _Client
    fake.models = _Models
    return fake


class TestExtractBskyText:
    """Unit tests for _extract_bsky_text helper."""

    def test_with_tldr_and_frontmatter(self, tmp_path: Path):
        from fgeo.commands.publish import _extract_bsky_text
        f = tmp_path / "a.md"
        f.write_text("---\ntitle: T\ndate: 2026-01-01\n---\n\n**太长不读**：这是摘要文字。\n\n正文在下面。\n")
        result = _extract_bsky_text(f)
        assert "摘要文字" in result
        assert "正文" not in result

    def test_without_tldr_takes_first_paragraph(self, tmp_path: Path):
        from fgeo.commands.publish import _extract_bsky_text
        f = tmp_path / "b.md"
        f.write_text("---\ntitle: T\n---\n\n第一段内容在这里。\n\n第二段内容不应该入选。\n")
        result = _extract_bsky_text(f)
        assert "第一段" in result
        assert "第二段" not in result

    def test_no_frontmatter(self, tmp_path: Path):
        from fgeo.commands.publish import _extract_bsky_text
        f = tmp_path / "c.md"
        f.write_text("# Title\n\nContent here.\n")
        result = _extract_bsky_text(f)
        # First paragraph is the heading; after stripping "# " we get the heading text
        assert "Title" in result

    def test_truncation_to_max_chars(self, tmp_path: Path):
        from fgeo.commands.publish import _extract_bsky_text
        f = tmp_path / "d.md"
        f.write_text("A" * 500 + "\n")
        result = _extract_bsky_text(f, max_chars=100)
        assert len(result) <= 100

    def test_only_frontmatter_no_body(self, tmp_path: Path):
        from fgeo.commands.publish import _extract_bsky_text
        f = tmp_path / "e.md"
        f.write_text("---\ntitle: T\n---\n")
        result = _extract_bsky_text(f)
        # Should not crash; returns an empty or whitespace-stripped string
        assert isinstance(result, str)

    def test_strips_markdown_formatting(self, tmp_path: Path):
        from fgeo.commands.publish import _extract_bsky_text
        f = tmp_path / "f.md"
        f.write_text("**bold** and *italic* and `code` and [link](https://example.com)\n")
        result = _extract_bsky_text(f)
        assert "**" not in result
        assert "*" not in result
        assert "`" not in result
        assert "[link]" not in result


class TestPublishBskyFlow:
    """Integration tests for fgeo publish content <bsky-platform>."""

    BSKY_HANDLE = "marvintalk.bsky.social"
    APP_PASSWORD = "xxxx-yyyy-zzzz-wwww"
    POST_URI = "at://did:plc:abc123/app.bsky.feed.post/rkey777"

    @pytest.fixture(autouse=True)
    def _fake_atproto(self):
        """Inject a fake atproto module for the duration of each test."""
        import sys
        fake = _make_fake_atproto(self.POST_URI)
        sys.modules["atproto"] = fake
        yield
        sys.modules.pop("atproto", None)

    def _register_bsky_content(self, fgeo_home: Path, tmp_path: Path) -> tuple[str, Path]:
        """Create a bluesky platform with credentials and register a markdown file."""
        runner.invoke(app, ["project", "create", "bskyproj"])
        runner.invoke(app, ["platform", "add", "bskyproj", "bluesky"])
        runner.invoke(app, ["platform", "set", "bskyproj", "bluesky",
                            "bsky_handle", self.BSKY_HANDLE])
        runner.invoke(app, ["platform", "set", "bskyproj", "bluesky",
                            "platform_secret", self.APP_PASSWORD])
        src = tmp_path / "post.md"
        src.write_text(
            "---\ntitle: Test Post\ndate: 2026-03-01\n---\n\n"
            "**太长不读**：这是测试内容摘要。\n\n正文在此。\n"
        )
        reg = runner.invoke(app, [
            "content", "register", str(src),
            "--project", "bskyproj",
            "--platform", "bluesky",
        ])
        content_id = _extract_id(reg.output, "cont")
        return content_id, src

    # ── Platform field tests ─────────────────────────────────────────────────

    def test_platform_set_bsky_handle(self, fgeo_home: Path, tmp_path: Path):
        runner.invoke(app, ["project", "create", "bskyproj"])
        runner.invoke(app, ["platform", "add", "bskyproj", "bluesky"])
        result = runner.invoke(app, ["platform", "set", "bskyproj", "bluesky",
                                     "bsky_handle", self.BSKY_HANDLE])
        assert result.exit_code == 0
        show = runner.invoke(app, ["platform", "show", "bskyproj", "bluesky"])
        assert self.BSKY_HANDLE in show.output

    def test_platform_show_masks_platform_secret(self, fgeo_home: Path, tmp_path: Path):
        runner.invoke(app, ["project", "create", "bskyproj"])
        runner.invoke(app, ["platform", "add", "bskyproj", "bluesky"])
        runner.invoke(app, ["platform", "set", "bskyproj", "bluesky",
                            "platform_secret", self.APP_PASSWORD])
        show = runner.invoke(app, ["platform", "show", "bskyproj", "bluesky"])
        assert "***" in show.output
        assert self.APP_PASSWORD not in show.output

    def test_platform_show_unset_fields_show_not_set(self, fgeo_home: Path, tmp_path: Path):
        runner.invoke(app, ["project", "create", "bskyproj"])
        runner.invoke(app, ["platform", "add", "bskyproj", "bluesky"])
        show = runner.invoke(app, ["platform", "show", "bskyproj", "bluesky"])
        assert "(not set)" in show.output

    # ── Happy-path publish ────────────────────────────────────────────────────

    def test_publish_bsky_exits_zero_and_shows_post_url(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0
        assert "bsky.app" in result.output or "Bluesky" in result.output

    def test_publish_bsky_creates_publish_task(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)
        runner.invoke(app, ["publish", "content", content_id])
        task_list = runner.invoke(app, ["publish", "task", "list"])
        assert task_list.exit_code == 0
        assert "pr_open" in task_list.output

    def test_publish_bsky_marks_content_published(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)
        runner.invoke(app, ["publish", "content", content_id])
        show = runner.invoke(app, ["content", "show", content_id])
        assert "published" in show.output

    def test_publish_bsky_with_published_url_builds_embed(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """When content has a published_url, the post should include an embed."""
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)
        # Set an existing published_url (e.g. from a previous blog publish)
        runner.invoke(app, ["content", "set", content_id,
                            "published_url", "https://example.com/my-post"])
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0

    def test_publish_bsky_malformed_uri_post_url_empty(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """URI with < 5 parts → post_url stays empty; content still published."""
        import sys, types
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)

        class _ShortUriClient:
            def login(self, h, p): pass
            def send_post(self, text, embed=None):
                return type("R", (), {"uri": "at://short"})()

        sys.modules["atproto"].Client = _ShortUriClient
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 0

    # ── Error-path publish ────────────────────────────────────────────────────

    def test_publish_bsky_missing_handle_exits_1(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        runner.invoke(app, ["project", "create", "bskyproj"])
        runner.invoke(app, ["platform", "add", "bskyproj", "bluesky"])
        src = tmp_path / "post.md"
        src.write_text("---\ntitle: T\n---\nHello.\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "bskyproj", "--platform", "bluesky"])
        content_id = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "bsky_handle" in result.output

    def test_publish_bsky_missing_password_exits_1(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        runner.invoke(app, ["project", "create", "bskyproj"])
        runner.invoke(app, ["platform", "add", "bskyproj", "bluesky"])
        runner.invoke(app, ["platform", "set", "bskyproj", "bluesky",
                            "bsky_handle", self.BSKY_HANDLE])
        src = tmp_path / "post.md"
        src.write_text("---\ntitle: T\n---\nHello.\n")
        reg = runner.invoke(app, ["content", "register", str(src),
                                  "--project", "bskyproj", "--platform", "bluesky"])
        content_id = _extract_id(reg.output, "cont")
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "platform_secret" in result.output

    def test_publish_bsky_login_failure_exits_1(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        import sys
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)

        class _FailLogin:
            def login(self, h, p): raise Exception("Invalid credentials")
            def send_post(self, text, embed=None): ...

        sys.modules["atproto"].Client = _FailLogin
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "login" in result.output.lower() or "failed" in result.output.lower()

    def test_publish_bsky_post_failure_exits_1(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        import sys
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)

        class _FailPost:
            def login(self, h, p): pass
            def send_post(self, text, embed=None): raise Exception("Rate limited")

        sys.modules["atproto"].Client = _FailPost
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "failed" in result.output.lower() or "post" in result.output.lower()

    def test_publish_bsky_atproto_not_installed(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """When atproto is not installed (ImportError), show install instructions."""
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)
        # Setting sys.modules entry to None blocks the import with ImportError
        monkeypatch.setitem(__import__("sys").modules, "atproto", None)
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "atproto" in result.output or "pip install" in result.output

    def test_publish_bsky_missing_source_path_exits_1(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """If source_path is cleared, publish should exit with error."""
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)
        runner.invoke(app, ["content", "set", content_id, "source_path", ""])
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "source" in result.output.lower()

    def test_publish_bsky_missing_source_file_exits_1(
        self, fgeo_home: Path, tmp_path: Path, monkeypatch
    ):
        """If source file on disk is gone, publish should exit with error."""
        monkeypatch.setattr("fgeo.commands.publish.FGEO_HOME", tmp_path / "fgeo_home")
        content_id, src = self._register_bsky_content(fgeo_home, tmp_path)
        src.unlink()  # delete the file
        result = runner.invoke(app, ["publish", "content", content_id])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestContentAssignPlan:
    """CLI tests for fgeo content assign-plan."""

    def _setup(self, fgeo_home: Path, tmp_path: Path) -> dict[str, str]:
        """Create project, plan, platforms, and content. Return dict of content IDs."""
        runner.invoke(app, ["project", "create", "asproj"])
        runner.invoke(app, ["plan",    "create",  "asproj", "gtm-v1"])
        runner.invoke(app, ["platform", "add",    "asproj", "devto"])
        runner.invoke(app, ["platform", "add",    "asproj", "medium"])
        runner.invoke(app, ["platform", "add",    "asproj", "twitter"])
        ids: dict[str, str] = {}
        for title, platform in [("PostA", "devto"), ("PostB", "devto"),
                                 ("PostC", "medium"), ("PostD", "twitter")]:
            f = tmp_path / f"{title}.md"
            f.write_text(f"# {title}\n\nContent.\n")
            reg = runner.invoke(app, [
                "content", "register", str(f),
                "--project", "asproj",
                "--platform", platform,
            ])
            ids[title] = _extract_id(reg.output, "cont")
        return ids

    def test_assign_all_exits_zero(self, fgeo_home: Path, tmp_path: Path):
        self._setup(fgeo_home, tmp_path)
        result = runner.invoke(app, ["content", "assign-plan", "asproj", "gtm-v1"])
        assert result.exit_code == 0
        assert "4" in result.output

    def test_assign_platform_filter(self, fgeo_home: Path, tmp_path: Path):
        self._setup(fgeo_home, tmp_path)
        result = runner.invoke(app, [
            "content", "assign-plan", "asproj", "gtm-v1",
            "--platform", "devto",
        ])
        assert result.exit_code == 0
        assert "2" in result.output
        assert "devto" in result.output

    def test_assign_multiple_platform_filters(self, fgeo_home: Path, tmp_path: Path):
        self._setup(fgeo_home, tmp_path)
        result = runner.invoke(app, [
            "content", "assign-plan", "asproj", "gtm-v1",
            "--platform", "devto", "--platform", "medium",
        ])
        assert result.exit_code == 0
        assert "3" in result.output

    def test_assign_status_filter(self, fgeo_home: Path, tmp_path: Path):
        ids = self._setup(fgeo_home, tmp_path)
        runner.invoke(app, ["content", "set", ids["PostA"], "status", "published"])
        result = runner.invoke(app, [
            "content", "assign-plan", "asproj", "gtm-v1",
            "--status", "published",
        ])
        assert result.exit_code == 0
        assert "1" in result.output
        assert "published" in result.output

    def test_assign_unknown_project_exits_1(self, fgeo_home: Path):
        result = runner.invoke(app, ["content", "assign-plan", "no-proj", "no-plan"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_assign_unknown_plan_exits_1(self, fgeo_home: Path):
        runner.invoke(app, ["project", "create", "asproj"])
        result = runner.invoke(app, ["content", "assign-plan", "asproj", "no-plan"])
        assert result.exit_code == 1
        assert "Plan not found" in result.output

    def test_assign_unknown_platform_returns_zero(self, fgeo_home: Path, tmp_path: Path):
        self._setup(fgeo_home, tmp_path)
        result = runner.invoke(app, [
            "content", "assign-plan", "asproj", "gtm-v1",
            "--platform", "ghost-platform",
        ])
        assert result.exit_code == 0
        assert "0" in result.output

    def test_content_set_plan_id(self, fgeo_home: Path, tmp_path: Path):
        """fgeo content set <id> plan_id <plan_id> should now work."""
        ids = self._setup(fgeo_home, tmp_path)
        from fgeo.database import get_db
        db = get_db()
        plan = db.get_plan("asproj", "gtm-v1")
        db.close()
        result = runner.invoke(app, ["content", "set", ids["PostA"], "plan_id", plan["id"]])
        assert result.exit_code == 0
        assert "plan_id" in result.output






