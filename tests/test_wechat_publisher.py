"""Tests for fgeo.publishers.wechat — Playwright RPA publisher (fully mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_page(*, logged_in: bool = True):
    """Build a mock Playwright page matching the real WeChat MP DOM (2026-03).

    Selectors used by the production code:
      textarea#title            — article title
      #author                   — author input
      #ueditor_0 .ProseMirror[contenteditable='true'] — rich editor div
      textarea#js_description   — digest / abstract
      #js_submit button         — save-draft button
    """
    page = MagicMock()

    # _is_logged_in: page.url controls redirect detection
    if logged_in:
        page.url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index&token=862082663"
    else:
        page.url = "https://mp.weixin.qq.com/cgi-bin/loginpage"

    # Per-selector mocks
    title_el = MagicMock()
    title_el.is_visible.return_value = True

    author_el = MagicMock()
    author_el.is_visible.return_value = True

    editor_el = MagicMock()
    editor_el.evaluate.return_value = "paste"
    editor_el.is_visible.return_value = True

    digest_el = MagicMock()
    digest_el.is_visible.return_value = True

    save_btn_el = MagicMock()
    save_btn_el.is_visible.return_value = True

    def _locator(selector: str):
        if "textarea#title" in selector or selector == "textarea#title":
            return title_el
        if selector == "#author":
            return author_el
        if "ProseMirror" in selector:
            return editor_el
        if "js_description" in selector:
            return digest_el
        if "js_submit" in selector:
            return save_btn_el
        # Default fallback
        return MagicMock()

    page.locator = _locator
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


class TestClearCookies:
    def test_deletes_existing_file(self, tmp_path: Path):
        from fgeo.publishers.wechat import _clear_cookies

        fake_file = tmp_path / "cookies.json"
        fake_file.write_text('[{"name": "sid"}]')
        with patch("fgeo.publishers.wechat.COOKIES_FILE", fake_file):
            _clear_cookies()
        assert not fake_file.exists()

    def test_noop_when_no_file(self, tmp_path: Path):
        from fgeo.publishers.wechat import _clear_cookies

        fake_file = tmp_path / "cookies.json"  # does not exist
        with patch("fgeo.publishers.wechat.COOKIES_FILE", fake_file):
            _clear_cookies()  # should not raise


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
        page.inner_text.return_value = "Welcome to WeChat MP"
        assert _is_logged_in(page) is True

    def test_not_logged_in_by_url(self):
        from fgeo.publishers.wechat import _is_logged_in

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/loginpage"
        assert _is_logged_in(page) is False

    def test_session_expired_text_detected(self):
        from fgeo.publishers.wechat import _is_logged_in

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index"
        page.inner_text.return_value = "Login timeout, Please Log in again."
        assert _is_logged_in(page) is False

    def test_inner_text_exception_swallowed(self):
        """If inner_text() raises, assume logged in — let later steps fail naturally."""
        from fgeo.publishers.wechat import _is_logged_in

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index"
        page.inner_text.side_effect = Exception("detached")
        assert _is_logged_in(page) is True

    def test_exception_returns_false(self):
        from fgeo.publishers.wechat import _is_logged_in

        page = MagicMock()
        page.goto.side_effect = Exception("network error")
        assert _is_logged_in(page) is False


class TestNavigateToEditor:
    def test_success_with_token(self):
        from fgeo.publishers.wechat import _navigate_to_editor

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&token=123"
        assert _navigate_to_editor(page, token="123") is True

    def test_success_without_token(self):
        from fgeo.publishers.wechat import _navigate_to_editor

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit"
        assert _navigate_to_editor(page) is True

    def test_redirected_to_login_returns_false(self):
        from fgeo.publishers.wechat import _navigate_to_editor

        page = MagicMock()
        page.url = "https://mp.weixin.qq.com/cgi-bin/loginpage"
        assert _navigate_to_editor(page, token="abc") is False

    def test_goto_exception_returns_false(self):
        from fgeo.publishers.wechat import _navigate_to_editor

        page = MagicMock()
        page.goto.side_effect = Exception("timeout")
        assert _navigate_to_editor(page) is False


class TestExtractToken:
    def test_extracts_token_from_url(self):
        from fgeo.publishers.wechat import _extract_token

        url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=en_US&token=862082663"
        assert _extract_token(url) == "862082663"

    def test_returns_empty_when_no_token(self):
        from fgeo.publishers.wechat import _extract_token

        assert _extract_token("https://mp.weixin.qq.com/cgi-bin/home") == ""

    def test_returns_empty_on_exception(self):
        from fgeo.publishers.wechat import _extract_token
        from unittest.mock import patch

        with patch("fgeo.publishers.wechat.urlparse", side_effect=Exception("boom")):
            assert _extract_token("https://example.com") == ""


class TestFillArticle:
    def test_basic_content_injection(self):
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page()
        result = _fill_article(page, "Test Title", "<p>Hello</p>")
        assert result is True

    def test_with_author_and_digest(self):
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page()
        result = _fill_article(page, "Test", "<p>Hi</p>", author="Marvin", digest="Summary")
        assert result is True

    def test_editor_not_found_returns_false(self):
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page()
        original_locator = page.locator

        def _fail_editor(selector: str):
            el = original_locator(selector)
            if "ProseMirror" in selector:
                el.wait_for.side_effect = Exception("editor not found")
            return el

        page.locator = _fail_editor
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
        page.locator.return_value = btn
        page.url = "https://mp.weixin.qq.com/cgi-bin/appmsg?action=edit&id=123"

        result = _save_draft(page)
        assert "appmsg" in result
        btn.click.assert_called_once()
        # Confirm the correct selector was used
        page.locator.assert_called_once_with("#js_submit button")

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

    def test_stale_cookies_cleared_on_session_expiry(self):
        """When saved cookies exist but session is expired, _clear_cookies is called."""
        from fgeo.publishers.wechat import publish_to_wechat

        import sys

        page = _make_mock_page(logged_in=False)
        cm, browser, context = _make_mock_playwright(page)

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        clear_mock = MagicMock()

        with patch("fgeo.publishers.wechat._check_playwright"), \
             patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "stale"}]), \
             patch("fgeo.publishers.wechat._save_cookies"), \
             patch("fgeo.publishers.wechat._clear_cookies", clear_mock), \
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

        clear_mock.assert_called_once()
        assert result["status"] == "draft_saved"


# ── Additional coverage tests ─────────────────────────────────────────────────


class TestFillArticleExceptionBranches:
    """Cover the except-pass branches in _fill_article (author + digest)."""

    def test_author_locator_raises_is_silenced(self):
        """If page.locator('#author') raises, the exception is swallowed (pass)."""
        from fgeo.publishers.wechat import _fill_article

        page = _make_mock_page()
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

        page = _make_mock_page()
        original_locator = page.locator

        def _locator_raise_on_digest(selector: str):
            if "js_description" in selector:
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
        with patch("fgeo.publishers.wechat._load_cookies", return_value=[{"name": "sid", "value": "x"}]), \
             patch("fgeo.publishers.wechat._clear_cookies"):
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


class TestInstallPlaywrightBrowsers:
    """Coverage for the new _install_playwright_browsers helper."""

    def test_success(self):
        from fgeo.publishers.wechat import _install_playwright_browsers

        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            _install_playwright_browsers()  # should not raise

    def test_failure_exits(self):
        from fgeo.publishers.wechat import _install_playwright_browsers

        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(SystemExit):
                _install_playwright_browsers()


class TestCheckPlaywrightBinaryBranches:
    """Coverage for _check_playwright binary-detection branches."""

    def test_binary_missing_triggers_install(self, tmp_path):
        """When executable_path does not exist, _install_playwright_browsers is called."""
        from fgeo.publishers.wechat import _check_playwright

        fake_pw_mod = MagicMock()
        fake_sync_ctx = MagicMock()
        fake_sync_ctx.__enter__ = MagicMock(return_value=fake_sync_ctx)
        fake_sync_ctx.__exit__ = MagicMock(return_value=False)
        fake_sync_ctx.chromium.executable_path = str(tmp_path / "nonexistent" / "chromium")
        fake_pw_mod.sync_playwright.return_value = fake_sync_ctx

        with patch.dict("sys.modules", {
            "playwright": fake_pw_mod,
            "playwright.sync_api": fake_pw_mod,
        }):
            with patch("fgeo.publishers.wechat._install_playwright_browsers") as mock_install:
                _check_playwright()
                mock_install.assert_called_once()

    def test_binary_exists_no_install(self, tmp_path):
        """When executable_path exists, _install_playwright_browsers is NOT called."""
        from fgeo.publishers.wechat import _check_playwright

        exe = tmp_path / "chromium"
        exe.touch()

        fake_pw_mod = MagicMock()
        fake_sync_ctx = MagicMock()
        fake_sync_ctx.__enter__ = MagicMock(return_value=fake_sync_ctx)
        fake_sync_ctx.__exit__ = MagicMock(return_value=False)
        fake_sync_ctx.chromium.executable_path = str(exe)
        fake_pw_mod.sync_playwright.return_value = fake_sync_ctx

        with patch.dict("sys.modules", {
            "playwright": fake_pw_mod,
            "playwright.sync_api": fake_pw_mod,
        }):
            with patch("fgeo.publishers.wechat._install_playwright_browsers") as mock_install:
                _check_playwright()
                mock_install.assert_not_called()

    def test_sync_playwright_exception_is_swallowed(self):
        """If sync_playwright() raises, the exception is caught and we continue."""
        from fgeo.publishers.wechat import _check_playwright

        fake_pw_mod = MagicMock()
        bad_sync = MagicMock(side_effect=RuntimeError("pw init error"))
        fake_pw_mod.sync_playwright = bad_sync

        with patch.dict("sys.modules", {
            "playwright": fake_pw_mod,
            "playwright.sync_api": fake_pw_mod,
        }):
            _check_playwright()  # should not raise

    def test_install_failure_propagates_system_exit(self, tmp_path):
        """SystemExit from _install_playwright_browsers propagates out (except SystemExit: raise)."""
        from fgeo.publishers.wechat import _check_playwright

        fake_pw_mod = MagicMock()
        fake_sync_ctx = MagicMock()
        fake_sync_ctx.__enter__ = MagicMock(return_value=fake_sync_ctx)
        fake_sync_ctx.__exit__ = MagicMock(return_value=False)
        fake_sync_ctx.chromium.executable_path = str(tmp_path / "nonexistent" / "chromium")
        fake_pw_mod.sync_playwright.return_value = fake_sync_ctx

        mock_result = MagicMock()
        mock_result.returncode = 1  # install fails → _install_playwright_browsers raises SystemExit

        with patch.dict("sys.modules", {
            "playwright": fake_pw_mod,
            "playwright.sync_api": fake_pw_mod,
        }):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(SystemExit):
                    _check_playwright()
