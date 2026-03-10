"""Tests for fgeo/publishers/juejin.py — 掘金 publisher."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures / helpers
# ══════════════════════════════════════════════════════════════════════════════


SAMPLE_COOKIES = [
    {"name": "sessionid", "value": "abc123", "domain": ".juejin.cn"},
    {"name": "uid_tt", "value": "xyz", "domain": ".juejin.cn"},
]


def _good_user_resp() -> MagicMock:
    """httpx response that indicates a logged-in user."""
    resp = MagicMock()
    resp.json.return_value = {"err_no": 0, "data": {"user_id": "12345"}}
    return resp


def _empty_user_resp() -> MagicMock:
    """httpx response with no user_id (logged-out)."""
    resp = MagicMock()
    resp.json.return_value = {"err_no": 0, "data": {}}
    return resp


def _draft_ok_resp(draft_id: str = "7000000000000000000") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"err_no": 0, "data": {"id": draft_id}}
    resp.raise_for_status.return_value = None
    return resp


def _draft_err_resp() -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"err_no": 403, "err_msg": "rate limit"}
    resp.raise_for_status.return_value = None
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# _ensure_data_dir
# ══════════════════════════════════════════════════════════════════════════════


class TestEnsureDataDir:
    def test_creates_directory(self, tmp_path: Path):
        from fgeo.publishers.juejin import _ensure_data_dir, JUEJIN_DATA_DIR

        with patch("fgeo.publishers.juejin.JUEJIN_DATA_DIR", tmp_path / "new_dir"):
            _ensure_data_dir()
            from fgeo.publishers import juejin
            assert juejin.JUEJIN_DATA_DIR.exists() or (tmp_path / "new_dir").exists()

    def test_creates_nested_directory(self, tmp_path: Path):
        from fgeo.publishers import juejin

        target = tmp_path / "a" / "b" / "c"
        with patch.object(juejin, "JUEJIN_DATA_DIR", target):
            juejin._ensure_data_dir()
        assert target.exists()


# ══════════════════════════════════════════════════════════════════════════════
# _save_cookies
# ══════════════════════════════════════════════════════════════════════════════


class TestSaveCookies:
    def test_writes_valid_json(self, tmp_path: Path):
        from fgeo.publishers import juejin

        with patch.object(juejin, "JUEJIN_DATA_DIR", tmp_path), \
             patch.object(juejin, "COOKIES_FILE", tmp_path / "cookies.json"), \
             patch.object(juejin, "_ensure_data_dir"):
            juejin._save_cookies(SAMPLE_COOKIES)

        saved = json.loads((tmp_path / "cookies.json").read_text())
        assert saved == SAMPLE_COOKIES

    def test_calls_ensure_data_dir(self, tmp_path: Path):
        from fgeo.publishers import juejin

        with patch.object(juejin, "COOKIES_FILE", tmp_path / "cookies.json"), \
             patch.object(juejin, "_ensure_data_dir") as mock_ensure:
            juejin._save_cookies(SAMPLE_COOKIES)
        mock_ensure.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# _load_cookies
# ══════════════════════════════════════════════════════════════════════════════


class TestLoadCookies:
    def test_returns_cookies_when_file_exists(self, tmp_path: Path):
        from fgeo.publishers import juejin

        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(SAMPLE_COOKIES), encoding="utf-8")
        with patch.object(juejin, "COOKIES_FILE", cookie_file):
            result = juejin._load_cookies()
        assert result == SAMPLE_COOKIES

    def test_returns_none_when_file_missing(self, tmp_path: Path):
        from fgeo.publishers import juejin

        with patch.object(juejin, "COOKIES_FILE", tmp_path / "no_file.json"):
            result = juejin._load_cookies()
        assert result is None

    def test_returns_none_on_invalid_json(self, tmp_path: Path):
        from fgeo.publishers import juejin

        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text("NOT JSON", encoding="utf-8")
        with patch.object(juejin, "COOKIES_FILE", cookie_file):
            result = juejin._load_cookies()
        assert result is None

    def test_returns_none_on_empty_list(self, tmp_path: Path):
        from fgeo.publishers import juejin

        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text("[]", encoding="utf-8")
        with patch.object(juejin, "COOKIES_FILE", cookie_file):
            result = juejin._load_cookies()
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# _clear_cookies
# ══════════════════════════════════════════════════════════════════════════════


class TestClearCookies:
    def test_deletes_existing_file(self, tmp_path: Path):
        from fgeo.publishers import juejin

        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text("[]")
        with patch.object(juejin, "COOKIES_FILE", cookie_file):
            juejin._clear_cookies()
        assert not cookie_file.exists()

    def test_silent_when_no_file(self, tmp_path: Path):
        from fgeo.publishers import juejin

        cookie_file = tmp_path / "no_file.json"
        with patch.object(juejin, "COOKIES_FILE", cookie_file):
            juejin._clear_cookies()  # should not raise


# ══════════════════════════════════════════════════════════════════════════════
# _cookies_to_header
# ══════════════════════════════════════════════════════════════════════════════


class TestCookiesToHeader:
    def test_single_cookie(self):
        from fgeo.publishers.juejin import _cookies_to_header

        cookies = [{"name": "sessionid", "value": "abc"}]
        assert _cookies_to_header(cookies) == "sessionid=abc"

    def test_multiple_cookies_joined_with_semicolon(self):
        from fgeo.publishers.juejin import _cookies_to_header

        result = _cookies_to_header(SAMPLE_COOKIES)
        assert "sessionid=abc123" in result
        assert "uid_tt=xyz" in result
        assert "; " in result

    def test_empty_list(self):
        from fgeo.publishers.juejin import _cookies_to_header

        assert _cookies_to_header([]) == ""


# ══════════════════════════════════════════════════════════════════════════════
# _is_logged_in
# ══════════════════════════════════════════════════════════════════════════════


class TestIsLoggedIn:
    def test_returns_true_when_user_id_present(self):
        from fgeo.publishers.juejin import _is_logged_in

        with patch("httpx.get", return_value=_good_user_resp()):
            assert _is_logged_in(SAMPLE_COOKIES) is True

    def test_returns_false_when_no_user_id(self):
        from fgeo.publishers.juejin import _is_logged_in

        with patch("httpx.get", return_value=_empty_user_resp()):
            assert _is_logged_in(SAMPLE_COOKIES) is False

    def test_returns_false_on_exception(self):
        from fgeo.publishers.juejin import _is_logged_in

        with patch("httpx.get", side_effect=Exception("network error")):
            assert _is_logged_in(SAMPLE_COOKIES) is False


# ══════════════════════════════════════════════════════════════════════════════
# _check_playwright
# ══════════════════════════════════════════════════════════════════════════════


class TestCheckPlaywright:
    def test_passes_when_playwright_installed(self):
        from fgeo.publishers.juejin import _check_playwright

        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "playwright":
                return MagicMock()
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            _check_playwright()  # should not raise

    def test_raises_when_playwright_missing(self):
        from fgeo.publishers.juejin import _check_playwright

        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "playwright":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(SystemExit):
                _check_playwright()


# ══════════════════════════════════════════════════════════════════════════════
# _do_browser_login
# ══════════════════════════════════════════════════════════════════════════════


def _make_playwright_cm(cookies: list[dict]):
    """Build a minimal fake playwright() context manager."""
    page = MagicMock()
    context = MagicMock()
    context.cookies.return_value = cookies
    browser = MagicMock()
    browser.new_context.return_value = context
    pw = MagicMock()
    pw.chromium.launch.return_value = browser
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=pw)
    cm.__exit__ = MagicMock(return_value=False)
    return cm, browser, context, page


class TestDoBrowserLogin:
    def test_returns_cookies_after_login(self):
        from fgeo.publishers.juejin import _do_browser_login

        cm, browser, context, _ = _make_playwright_cm(SAMPLE_COOKIES)
        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.juejin._check_playwright"), \
             patch("fgeo.publishers.juejin._ensure_data_dir"), \
             patch("fgeo.publishers.juejin._save_cookies") as mock_save, \
             patch("builtins.input", return_value=""):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = _do_browser_login()
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result == SAMPLE_COOKIES
        mock_save.assert_called_once_with(SAMPLE_COOKIES)

    def test_browser_closed_after_login(self):
        from fgeo.publishers.juejin import _do_browser_login

        cm, browser, context, _ = _make_playwright_cm(SAMPLE_COOKIES)
        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        with patch("fgeo.publishers.juejin._check_playwright"), \
             patch("fgeo.publishers.juejin._ensure_data_dir"), \
             patch("fgeo.publishers.juejin._save_cookies"), \
             patch("builtins.input", return_value=""):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                _do_browser_login()
            finally:
                sys.modules.pop("playwright.sync_api", None)

        browser.close.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# _get_cookies
# ══════════════════════════════════════════════════════════════════════════════


class TestGetCookies:
    def test_returns_saved_valid_cookies(self):
        from fgeo.publishers.juejin import _get_cookies

        with patch("fgeo.publishers.juejin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._is_logged_in", return_value=True):
            result = _get_cookies()
        assert result == SAMPLE_COOKIES

    def test_does_browser_login_when_no_cookies(self):
        from fgeo.publishers.juejin import _get_cookies

        with patch("fgeo.publishers.juejin._load_cookies", return_value=None), \
             patch("fgeo.publishers.juejin._do_browser_login", return_value=SAMPLE_COOKIES) as mock_login:
            result = _get_cookies()
        assert result == SAMPLE_COOKIES
        mock_login.assert_called_once()

    def test_clears_and_relogins_when_cookies_expired(self):
        from fgeo.publishers.juejin import _get_cookies

        with patch("fgeo.publishers.juejin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._is_logged_in", return_value=False), \
             patch("fgeo.publishers.juejin._clear_cookies") as mock_clear, \
             patch("fgeo.publishers.juejin._do_browser_login", return_value=SAMPLE_COOKIES) as mock_login:
            result = _get_cookies()
        mock_clear.assert_called_once()
        mock_login.assert_called_once()
        assert result == SAMPLE_COOKIES


# ══════════════════════════════════════════════════════════════════════════════
# _create_draft
# ══════════════════════════════════════════════════════════════════════════════


class TestCreateDraft:
    def test_returns_json_on_success(self):
        from fgeo.publishers.juejin import _create_draft

        expected = {"err_no": 0, "data": {"id": "7123"}}
        resp = MagicMock()
        resp.json.return_value = expected
        resp.raise_for_status.return_value = None

        with patch("httpx.post", return_value=resp):
            result = _create_draft(SAMPLE_COOKIES, "Title", "# Body", "6809637767543259144", [])

        assert result == expected

    def test_uses_brief_content_from_arg(self):
        from fgeo.publishers.juejin import _create_draft

        resp = _draft_ok_resp()
        with patch("httpx.post", return_value=resp) as mock_post:
            _create_draft(SAMPLE_COOKIES, "T", "# MD", "123", [], brief_content="Short desc")

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["brief_content"] == "Short desc"

    def test_defaults_brief_content_to_title(self):
        from fgeo.publishers.juejin import _create_draft

        resp = _draft_ok_resp()
        with patch("httpx.post", return_value=resp) as mock_post:
            _create_draft(SAMPLE_COOKIES, "My Title", "# MD", "123", [])

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["brief_content"] == "My Title"

    def test_raises_runtime_error_when_httpx_missing(self):
        from fgeo.publishers.juejin import _create_draft

        with patch.dict(sys.modules, {"httpx": None}):
            # Force reimport without httpx; but since the import is inline, we patch it
            with pytest.raises(RuntimeError, match="httpx not installed"):
                _create_draft(SAMPLE_COOKIES, "T", "# MD", "123", [])

    def test_raises_for_status_called(self):
        from fgeo.publishers.juejin import _create_draft

        resp = _draft_ok_resp()
        with patch("httpx.post", return_value=resp):
            _create_draft(SAMPLE_COOKIES, "T", "# MD", "123", [])
        resp.raise_for_status.assert_called_once()

    def test_sets_edit_type_markdown(self):
        from fgeo.publishers.juejin import _create_draft

        resp = _draft_ok_resp()
        with patch("httpx.post", return_value=resp) as mock_post:
            _create_draft(SAMPLE_COOKIES, "T", "# MD", "123", [42])

        payload = mock_post.call_args.kwargs["json"]
        assert payload["edit_type"] == 10
        assert payload["tag_ids"] == [42]


# ══════════════════════════════════════════════════════════════════════════════
# publish_to_juejin
# ══════════════════════════════════════════════════════════════════════════════


class TestPublishToJuejin:
    def test_success_returns_draft_url(self, tmp_path: Path):
        from fgeo.publishers.juejin import publish_to_juejin

        draft_id = "7000000000000099999"
        with patch("fgeo.publishers.juejin._get_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._create_draft", return_value={"err_no": 0, "data": {"id": draft_id}}):
            result = publish_to_juejin("Title", "# Body", task_dir=tmp_path)

        assert result["status"] == "draft_saved"
        assert draft_id in result["url"]
        assert result["id"] == draft_id

    def test_returns_failed_when_httpx_missing(self):
        from fgeo.publishers.juejin import publish_to_juejin

        with patch.dict(sys.modules, {"httpx": None}):
            result = publish_to_juejin("Title", "# Body")

        assert result["status"] == "failed"
        assert "httpx" in result["message"].lower()

    def test_returns_failed_when_login_raises(self):
        from fgeo.publishers.juejin import publish_to_juejin

        with patch("fgeo.publishers.juejin._get_cookies", side_effect=Exception("auth error")):
            result = publish_to_juejin("Title", "# Body")

        assert result["status"] == "failed"
        assert "Login failed" in result["message"]

    def test_returns_failed_when_create_draft_raises(self):
        from fgeo.publishers.juejin import publish_to_juejin

        with patch("fgeo.publishers.juejin._get_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._create_draft", side_effect=Exception("network error")):
            result = publish_to_juejin("Title", "# Body")

        assert result["status"] == "failed"
        assert "network error" in result["message"]

    def test_returns_failed_when_api_error_code(self):
        from fgeo.publishers.juejin import publish_to_juejin

        with patch("fgeo.publishers.juejin._get_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._create_draft", return_value={"err_no": 403, "err_msg": "rate limit"}):
            result = publish_to_juejin("Title", "# Body")

        assert result["status"] == "failed"
        assert "403" in result["message"]
        assert "rate limit" in result["message"]

    def test_uses_default_category_id(self):
        from fgeo.publishers.juejin import publish_to_juejin, JUEJIN_DEFAULT_CATEGORY

        with patch("fgeo.publishers.juejin._get_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._create_draft", return_value={"err_no": 0, "data": {"id": "7111"}}) as mock_draft:
            publish_to_juejin("Title", "# Body")

        _, call_kwargs = mock_draft.call_args
        # category_id is positional arg 3
        assert JUEJIN_DEFAULT_CATEGORY in mock_draft.call_args[1].get("category_id", mock_draft.call_args[0][3] if len(mock_draft.call_args[0]) > 3 else JUEJIN_DEFAULT_CATEGORY)

    def test_passes_custom_category_and_tags(self):
        from fgeo.publishers.juejin import publish_to_juejin

        custom_cat = "6809637767543259944"
        with patch("fgeo.publishers.juejin._get_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._create_draft", return_value={"err_no": 0, "data": {"id": "7222"}}) as mock_draft:
            publish_to_juejin("Title", "# Body", category_id=custom_cat, tag_ids=[1, 2])

        kwargs = mock_draft.call_args[1]
        assert kwargs["category_id"] == custom_cat
        assert kwargs["tag_ids"] == [1, 2]

    def test_draft_url_built_from_id(self):
        from fgeo.publishers.juejin import publish_to_juejin

        with patch("fgeo.publishers.juejin._get_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin._create_draft", return_value={"err_no": 0, "data": {"id": "7abc"}}):
            result = publish_to_juejin("T", "# B")

        assert result["url"] == "https://juejin.cn/editor/drafts/7abc"
