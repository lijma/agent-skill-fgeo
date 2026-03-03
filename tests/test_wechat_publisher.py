"""Tests for fgeo.publishers.wechat — Playwright RPA publisher (fully mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_page(*, logged_in: bool = True, iframe_editor: bool = True):
    """Build a mock Playwright page with configurable behaviour."""
    page = MagicMock()

    # _is_logged_in: page.url controls redirect detection
    if logged_in:
        page.url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index"
    else:
        page.url = "https://mp.weixin.qq.com/cgi-bin/loginpage"

    # Locators returned by page.locator(...)
    title_input = MagicMock()
    title_input.is_visible.return_value = True

    author_input = MagicMock()
    author_input.is_visible.return_value = True

    digest_input = MagicMock()
    digest_input.is_visible.return_value = True

    save_btn = MagicMock()
    save_btn.is_visible.return_value = True

    # Editor element (body inside iframe or div)
    editor_el = MagicMock()
    editor_el.evaluate.return_value = "paste"  # ClipboardEvent succeeded

    def _locator(selector: str):
        if selector == "#title":
            return title_input
        if selector == "#author":
            return author_input
        if "textarea" in selector:
            loc = MagicMock()
            loc.first = digest_input
            return loc
        if "has-text" in selector:
            loc = MagicMock()
            loc.first = save_btn
            return loc
        # contenteditable fallback
        loc = MagicMock()
        loc.first = editor_el
        return loc

    page.locator = _locator

    # Frame locator for iframe editor
    if iframe_editor:
        frame_loc = MagicMock()
        body_loc = MagicMock()
        body_loc.evaluate.return_value = "paste"
        frame_loc.locator.return_value = body_loc
        page.frame_locator = MagicMock(return_value=frame_loc)
    else:
        # iframe not found → raise so fallback kicks in
        page.frame_locator = MagicMock(side_effect=Exception("no iframe"))

    return page


def _make_mock_playwright(page: MagicMock, cookies: list | None = None):
    """Build a mock sync_playwright context manager."""
    browser = MagicMock()
    context = MagicMock()
    context.new_page.return_value = page
    context.cookies.return_value = cookies or [{"name": "sid", "value": "abc"}]
    browser.new_context.return_value = context

    pw = MagicMock()
    pw.chromium.launch.return_value = browser

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=pw)
    cm.__exit__ = MagicMock(return_value=False)

    return cm, browser, context


# ── Unit tests for helper functions ──────────────────────────────────────────


class TestEnsureDataDir:
    def test_creates_directory(self, tmp_path: Path):
        from fgeo.publishers.wechat import _ensure_data_dir

        fake_dir = tmp_path / "wechat"
        with patch("fgeo.publishers.wechat.WECHAT_DATA_DIR", fake_dir):
            _ensure_data_dir()
        assert fake_dir.is_dir()

    def test_idempotent(self, tmp_path: Path):
        from fgeo.publishers.wechat import _ensure_data_dir

        fake_dir = tmp_path / "wechat"
        fake_dir.mkdir()
        with patch("fgeo.publishers.wechat.WECHAT_DATA_DIR", fake_dir):
            _ensure_data_dir()  # should not raise
        assert fake_dir.is_dir()


class TestSaveCookies:
    def test_saves_json(self, tmp_path: Path):
        from fgeo.publishers.wechat import _save_cookies

        fake_dir = tmp_path / "wechat"
        fake_file = fake_dir / "cookies.json"
        with patch("fgeo.publishers.wechat.WECHAT_DATA_DIR", fake_dir), \
             patch("fgeo.publishers.wechat.COOKIES_FILE", fake_file):
            _save_cookies([{"name": "sid", "value": "123"}])

        assert fake_file.exists()
        data = json.loads(fake_file.read_text())
        assert data[0]["name"] == "sid"


class TestLoadCookies:
    def test_loads_existing(self, tmp_path: Path):
        from fgeo.publishers.wechat import _load_cookies

        fake_file = tmp_path / "cookies.json"
        fake_file.write_text('[{"name": "sid", "value": "abc"}]')
        with patch("fgeo.publishers.wechat.COOKIES_FILE", fake_file):
            result = _load_cookies()
        assert result is not None
        assert result[0]["value"] == "abc"

    def test_returns_none_when_missing(self, tmp_path: Path):
        from fgeo.publishers.wechat import _load_cookies

        fake_file = tmp_path / "cookies.json"
        with patch("fgeo.publishers.wechat.COOKIES_FILE", fake_file):
            assert _load_cookies() is None

    def test_returns_none_on_bad_json(self, tmp_path: Path):
        from fgeo.publishers.wechat import _load_cookies

        fake_file = tmp_path / "cookies.json"
        fake_file.write_text("not valid json!!!")
        with patch("fgeo.publishers.wechat.COOKIES_FILE", fake_file):
            assert _load_cookies() is None

    def test_returns_none_on_empty_list(self, tmp_path: Path):
        from fgeo.publishers.wechat import _load_cookies

        fake_file = tmp_path / "cookies.json"
        fake_file.write_text("[]")
        with patch("fgeo.publishers.wechat.COOKIES_FILE", fake_file):
            assert _load_cookies() is None


class TestCheckPlaywright:
    def test_passes_when_installed(self):
        from fgeo.publishers.wechat import _check_playwright

        with patch.dict("sys.modules", {"playwright": MagicMock()}):
            _check_playwright()  # should not raise

    def test_exits_when_missing(self):
        import builtins

        from fgeo.publishers.wechat import _check_playwright

        real_import = builtins.__import__

        def _selective_import(name, *args, **kwargs):
            if name == "playwright":
                raise ImportError("no playwright")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_selective_import):
            with pytest.raises(SystemExit):
                _check_playwright()


class TestLoginWithQr:
    def test_success(self):
        from fgeo.publishers.wechat import _login_with_qr

        page = MagicMock()
        page.wait_for_url.return_value = None  # completes without error
        assert _login_with_qr(page) is True

    def test_timeout(self):
        from fgeo.publishers.wechat import _login_with_qr

        page = MagicMock()
        page.wait_for_url.side_effect = TimeoutError("timed out")
        assert _login_with_qr(page) is False


class TestIsLoggedIn:
    def test_logged_in(self):
        from fgeo.publishers.wechat import _is_logged_in

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index"
        assert _is_logged_in(page) is True

    def test_not_logged_in(self):
        from fgeo.publishers.wechat import _is_logged_in

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/loginpage"
        assert _is_logged_in(page) is False

    def test_exception_returns_false(self):
        from fgeo.publishers.wechat import _is_logged_in

        page = MagicMock()
        page.goto.side_effect = Exception("network error")
        assert _is_logged_in(page) is False


class TestNavigateToEditor:
    def test_success(self):
        from fgeo.publishers.wechat import _navigate_to_editor

        page = MagicMock()
        assert _navigate_to_editor(page) is True

    def test_failure(self):
        from fgeo.publishers.wechat import _navigate_to_editor

        page = MagicMock()
        page.goto.side_effect = Exception("timeout")
        assert _navigate_to_editor(page) is False


class TestFillArticle:
    def test_iframe_editor_paste(self):
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page(iframe_editor=True)
        result = _fill_article(page, "Test Title", "<p>Hello</p>")
        assert result is True

    def test_div_editor_fallback(self):
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page(iframe_editor=False)
        result = _fill_article(page, "Test Title", "<p>Hello</p>")
        assert result is True

    def test_with_author_and_digest(self):
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page(iframe_editor=True)
        result = _fill_article(page, "Test", "<p>Hi</p>", author="Marvin", digest="Summary")
        assert result is True

    def test_no_editor_found_returns_false(self):
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page(iframe_editor=False)
        # Make div locator also fail
        original_locator = page.locator

        def _fail_all(selector):
            loc = original_locator(selector)
            if "ProseMirror" in selector or "contenteditable" in selector:
                loc.first.wait_for.side_effect = Exception("no editor")
            return loc

        page.locator = _fail_all
        result = _fill_article(page, "Test", "<p>Hi</p>")
        assert result is False

    def test_title_exception_returns_false(self):
        from fgeo.publishers.wechat import _fill_article

        page = MagicMock()
        page.locator.side_effect = Exception("boom")
        result = _fill_article(page, "T", "<p>x</p>")
        assert result is False


class TestSaveDraft:
    def test_clicks_and_returns_url(self):
        from fgeo.publishers.wechat import _save_draft

        page = MagicMock()
        btn = MagicMock()
        btn.is_visible.return_value = True
        loc = MagicMock()
        loc.first = btn
        page.locator.return_value = loc
        page.url = "https://mp.weixin.qq.com/cgi-bin/appmsg?action=edit&id=123"

        result = _save_draft(page)
        assert "appmsg" in result
        btn.click.assert_called_once()

    def test_exception_returns_empty(self):
        from fgeo.publishers.wechat import _save_draft

        page = MagicMock()
        page.locator.side_effect = Exception("no button")
        result = _save_draft(page)
        assert result == ""


# ── Integration tests for publish_to_wechat ──────────────────────────────────


class TestPublishToWechat:
    """End-to-end tests for publish_to_wechat with fully mocked Playwright."""

    def test_happy_path_saves_draft(self, tmp_path: Path):
        from fgeo.publishers.wechat import publish_to_wechat

        page = _make_mock_page(logged_in=True)
        cm, browser, context = _make_mock_playwright(page)

        import sys

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "s"}]), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=True), \
             patch("fgeo.publishers.wechat._navigate_to_editor", return_value=True), \
             patch("fgeo.publishers.wechat._fill_article", return_value=True), \
             patch("fgeo.publishers.wechat._save_draft", return_value="https://mp.weixin.qq.com/draft/123"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(
                    title="Test Article",
                    html_content="<section><p>Hello</p></section>",
                    task_dir=tmp_path / "task",
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "draft_saved"
        assert "mp.weixin.qq.com" in result["url"]

    def test_login_failure(self, tmp_path: Path):
        from fgeo.publishers.wechat import publish_to_wechat

        page = _make_mock_page(logged_in=False)
        cm, browser, context = _make_mock_playwright(page)

        import sys

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=None), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=False), \
             patch("fgeo.publishers.wechat._login_with_qr", return_value=False):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(
                    title="Fail Login",
                    html_content="<p>test</p>",
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "Login" in result["message"] or "login" in result["message"].lower()

    def test_editor_navigation_failure(self, tmp_path: Path):
        from fgeo.publishers.wechat import publish_to_wechat

        page = _make_mock_page(logged_in=True)
        cm, browser, context = _make_mock_playwright(page)

        import sys

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "s"}]), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=True), \
             patch("fgeo.publishers.wechat._navigate_to_editor", return_value=False):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(
                    title="No Editor",
                    html_content="<p>test</p>",
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "editor" in result["message"].lower() or "navigate" in result["message"].lower()

    def test_fill_article_failure(self, tmp_path: Path):
        from fgeo.publishers.wechat import publish_to_wechat

        page = _make_mock_page(logged_in=True)
        cm, browser, context = _make_mock_playwright(page)

        import sys

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "s"}]), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=True), \
             patch("fgeo.publishers.wechat._navigate_to_editor", return_value=True), \
             patch("fgeo.publishers.wechat._fill_article", return_value=False):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(
                    title="Fill Failed",
                    html_content="<p>test</p>",
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "content" in result["message"].lower() or "insert" in result["message"].lower()

    def test_task_dir_saves_html(self, tmp_path: Path):
        from fgeo.publishers.wechat import publish_to_wechat

        page = _make_mock_page(logged_in=True)
        cm, browser, context = _make_mock_playwright(page)
        task_dir = tmp_path / "artifacts"

        import sys

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "s"}]), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=True), \
             patch("fgeo.publishers.wechat._navigate_to_editor", return_value=True), \
             patch("fgeo.publishers.wechat._fill_article", return_value=True), \
             patch("fgeo.publishers.wechat._save_draft", return_value="https://mp.weixin.qq.com/draft/1"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                publish_to_wechat(
                    title="HTML Save Test",
                    html_content="<section>content</section>",
                    task_dir=task_dir,
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert (task_dir / "article.html").exists()
        assert "<section>content</section>" in (task_dir / "article.html").read_text()

    def test_save_only_false_still_saves_draft(self, tmp_path: Path):
        """When save_only=False, we still save draft (direct publish not implemented)."""
        from fgeo.publishers.wechat import publish_to_wechat

        page = _make_mock_page(logged_in=True)
        cm, browser, context = _make_mock_playwright(page)

        import sys

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "s"}]), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=True), \
             patch("fgeo.publishers.wechat._navigate_to_editor", return_value=True), \
             patch("fgeo.publishers.wechat._fill_article", return_value=True), \
             patch("fgeo.publishers.wechat._save_draft", return_value="https://mp.weixin.qq.com/draft/1"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(
                    title="Publish Attempt",
                    html_content="<p>test</p>",
                    save_only=False,
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "draft_saved"


# ── Additional coverage tests ─────────────────────────────────────────────────


class TestFillArticleExceptionBranches:
    """Cover the except-pass branches in _fill_article (author + digest)."""

    def test_author_locator_raises_is_silenced(self):
        """If page.locator('#author') raises, the exception is swallowed (pass)."""
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page(iframe_editor=True)
        original_locator = page.locator

        def _locator_raise_on_author(selector: str):
            if selector == "#author":
                raise RuntimeError("author field not found")
            return original_locator(selector)

        page.locator = _locator_raise_on_author
        # Should not raise; exception is caught and silenced
        result = _fill_article(page, "Title", "<p>body</p>", author="Marvin")
        assert result is True

    def test_digest_locator_raises_is_silenced(self):
        """If the digest locator raises, the exception is swallowed (pass)."""
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page(iframe_editor=True)
        original_locator = page.locator

        def _locator_raise_on_digest(selector: str):
            if "textarea" in selector:
                raise RuntimeError("digest field missing")
            return original_locator(selector)

        page.locator = _locator_raise_on_digest
        result = _fill_article(page, "Title", "<p>body</p>", digest="A summary")
        assert result is True


class TestPublishToWechatHeadlessAndEdgePaths:
    """Cover headless relaunch, post-QR cookie save, and unexpected exception."""

    def _run_with_mocked_pw(self, page, cm, *, is_logged_in, login_qr_result=True, extra_patches=None):
        """Helper: run publish_to_wechat with fully mocked Playwright."""
        import sys

        from fgeo.publishers.wechat import publish_to_wechat

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        patches = {
            "fgeo.publishers.wechat._check_playwright": MagicMock(),
            "fgeo.publishers.wechat._save_cookies": MagicMock(),
        }
        if extra_patches:
            patches.update(extra_patches)

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=is_logged_in), \
             patch("fgeo.publishers.wechat._login_with_qr", return_value=login_qr_result), \
             patch("fgeo.publishers.wechat._navigate_to_editor", return_value=True), \
             patch("fgeo.publishers.wechat._fill_article", return_value=True), \
             patch("fgeo.publishers.wechat._save_draft", return_value="https://mp.weixin.qq.com/draft/1"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(
                    title="T",
                    html_content="<p>x</p>",
                    headless=True,
                    save_only=True,
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)
        return result

    def test_headless_with_cookies_not_logged_in_relaunches_headed(self):
        """When headless=True, cookies exist, but not logged in → relaunch headed and QR scan."""
        page = _make_mock_page(logged_in=False)
        cm, browser, context = _make_mock_playwright(page, cookies=[{"name": "sid", "value": "x"}])

        # _load_cookies returns saved cookies → launch_headless=True
        # _is_logged_in returns False → headless relaunch path + QR login
        with patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "sid", "value": "x"}]):
            result = self._run_with_mocked_pw(page, cm, is_logged_in=False, login_qr_result=True)

        assert result["status"] == "draft_saved"

    def test_qr_login_success_saves_cookies(self):
        """After successful QR login, _save_cookies is called with context cookies (line 341)."""
        from unittest.mock import call

        page = _make_mock_page(logged_in=False)
        cm, browser, context = _make_mock_playwright(page)

        import sys

        from fgeo.publishers.wechat import publish_to_wechat

        save_mock = MagicMock()
        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=None), \
             patch("fgeo.publishers.wechat._save_cookies", save_mock), \
             patch("fgeo.publishers.wechat._is_logged_in", return_value=False), \
             patch("fgeo.publishers.wechat._login_with_qr", return_value=True), \
             patch("fgeo.publishers.wechat._navigate_to_editor", return_value=True), \
             patch("fgeo.publishers.wechat._fill_article", return_value=True), \
             patch("fgeo.publishers.wechat._save_draft", return_value="https://mp.weixin.qq.com/draft/1"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(title="T", html_content="<p>x</p>")
            finally:
                sys.modules.pop("playwright.sync_api", None)

        # _save_cookies should have been called (at least once after QR login)
        assert save_mock.call_count >= 1
        assert result["status"] == "draft_saved"

    def test_unexpected_exception_sets_failed_status(self):
        """If an unexpected exception is raised in the try block, result is failed."""
        import sys

        from fgeo.publishers.wechat import publish_to_wechat

        page = _make_mock_page(logged_in=True)
        cm, browser, context = _make_mock_playwright(page)

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "s"}]), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._is_logged_in", side_effect=RuntimeError("boom")):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_wechat(title="T", html_content="<p>x</p>")
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "boom" in result["message"]
