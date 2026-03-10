"""Tests for fgeo/publishers/juejin_pin.py — 掘金沸点 Playwright RPA publisher."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SAMPLE_COOKIES = [
    {"name": "sessionid", "value": "abc123", "domain": ".juejin.cn"},
    {"name": "uid_tt", "value": "xyz", "domain": ".juejin.cn"},
]


# ── Mock helpers ──────────────────────────────────────────────────────────────


def _make_pw_mocks(pin_data: dict | None = None):
    """Build a fully-mocked Playwright chain for juejin_pin tests.

    When *pin_data* is provided, clicking the submit button will trigger the
    registered ``page.on("response", handler)`` callback with a successful
    API response containing that data.

    Returns ``(fake_pw_mod, page, response_handlers)``.
    """
    response_handlers: list = []

    page = MagicMock()

    # Capture any response handlers registered via page.on("response", ...)
    def _on_side_effect(event_name: str, handler) -> None:
        if event_name == "response":
            response_handlers.append(handler)

    page.on.side_effect = _on_side_effect

    # Build the submit button that triggers the response callback on click.
    submit_btn = MagicMock()
    if pin_data is not None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json.return_value = {"err_no": 0, "data": pin_data}

        def _click_side_effect() -> None:
            for h in response_handlers:
                h(mock_resp)

        submit_btn.click.side_effect = _click_side_effect

    editor_el = MagicMock()

    def _locator(selector: str):
        if "rich-editor" in selector:
            return editor_el
        if "submit" in selector:
            return submit_btn
        return MagicMock()

    page.locator.side_effect = _locator

    # Wire up browser → context → page
    context = MagicMock()
    context.new_page.return_value = page
    browser = MagicMock()
    browser.new_context.return_value = context
    pw = MagicMock()
    pw.chromium.launch.return_value = browser

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=pw)
    cm.__exit__ = MagicMock(return_value=False)

    fake_pw_mod = MagicMock()
    fake_pw_mod.sync_playwright.return_value = cm

    return fake_pw_mod, page, response_handlers


def _run_post_pin(pin_data=None, text="Hello pin!"):
    """Helper: call _post_pin_playwright with mocked Playwright."""
    from fgeo.publishers.juejin_pin import _post_pin_playwright

    fake_pw_mod, page, _ = _make_pw_mocks(pin_data)
    with patch("fgeo.publishers.juejin_pin._check_playwright"), \
         patch("time.sleep"), \
         patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
        return _post_pin_playwright(SAMPLE_COOKIES, text), page


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_max_chars(self):
        from fgeo.publishers.juejin_pin import JUEJIN_PIN_MAX_CHARS
        assert JUEJIN_PIN_MAX_CHARS == 1000

    def test_pins_url(self):
        from fgeo.publishers.juejin_pin import JUEJIN_PINS_URL
        assert "juejin.cn/pins" in JUEJIN_PINS_URL


# ══════════════════════════════════════════════════════════════════════════════
# _post_pin_playwright
# ══════════════════════════════════════════════════════════════════════════════


class TestPostPinPlaywright:
    def test_navigates_to_pins_url(self):
        from fgeo.publishers.juejin_pin import JUEJIN_PINS_URL
        _, page = _run_post_pin({"pin_id": "7001"})
        page.goto.assert_called_once()
        assert page.goto.call_args[0][0] == JUEJIN_PINS_URL

    def test_types_text_in_editor(self):
        _, page = _run_post_pin({"pin_id": "7001"}, text="My content")
        page.keyboard.type.assert_called_once_with("My content")

    def test_editor_is_clicked_before_typing(self):
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, _ = _make_pw_mocks({"pin_id": "7001"})
        call_order = []

        # Capture call order of editor.click and keyboard.type
        editor_el = MagicMock()
        editor_el.click.side_effect = lambda: call_order.append("click")
        submit_btn = MagicMock()

        def _locator(sel):
            if "rich-editor" in sel:
                return editor_el
            return submit_btn

        page.locator.side_effect = _locator
        page.keyboard.type.side_effect = lambda *a: call_order.append("type")

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            _post_pin_playwright(SAMPLE_COOKIES, "hi")

        assert call_order.index("click") < call_order.index("type")

    def test_submit_button_is_clicked(self):
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, _ = _make_pw_mocks({"pin_id": "7001"})
        submit_btn = MagicMock()

        def _locator(sel):
            if "rich-editor" in sel:
                return MagicMock()
            if "submit" in sel:
                return submit_btn
            return MagicMock()

        page.locator.side_effect = _locator
        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            _post_pin_playwright(SAMPLE_COOKIES, "hi")

        submit_btn.click.assert_called_once()

    def test_adds_cookies_to_context(self):
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, _ = _make_pw_mocks({"pin_id": "7001"})
        # Retrieve the context mock from the chain
        pw_instance = fake_pw_mod.sync_playwright.return_value.__enter__.return_value
        context = pw_instance.chromium.launch.return_value.new_context.return_value

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            _post_pin_playwright(SAMPLE_COOKIES, "hi")

        context.add_cookies.assert_called_once_with(SAMPLE_COOKIES)

    def test_returns_captured_pin_id_data(self):
        result, _ = _run_post_pin({"pin_id": "7123456789"})
        assert result.get("pin_id") == "7123456789"

    def test_returns_empty_when_no_response(self):
        # pin_data=None → submit click does NOT trigger response handler
        result, _ = _run_post_pin(pin_data=None)
        assert result == {}

    def test_ignores_non_200_response(self):
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, response_handlers = _make_pw_mocks()
        # Non-200 and >= 400 should be ignored
        non_400_resp = MagicMock()
        non_400_resp.status = 403

        submit_btn = MagicMock()

        def _click():
            for h in response_handlers:
                h(non_400_resp)

        submit_btn.click.side_effect = _click

        def _locator(sel):
            if "rich-editor" in sel:
                return MagicMock()
            if "submit" in sel:
                return submit_btn
            return MagicMock()

        page.locator.side_effect = _locator

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            result = _post_pin_playwright(SAMPLE_COOKIES, "hi")

        assert result == {}

    def test_accepts_2xx_non_200_response(self):
        """Status 201 is a valid success response and should be captured."""
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, response_handlers = _make_pw_mocks()
        resp_201 = MagicMock()
        resp_201.status = 201
        resp_201.json.return_value = {"err_no": 0, "data": {"short_msg_id": "7999"}}

        submit_btn = MagicMock()

        def _click():
            for h in response_handlers:
                h(resp_201)

        submit_btn.click.side_effect = _click

        def _locator(sel):
            if "rich-editor" in sel:
                return MagicMock()
            if "submit" in sel:
                return submit_btn
            return MagicMock()

        page.locator.side_effect = _locator

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            result = _post_pin_playwright(SAMPLE_COOKIES, "hi")

        assert result.get("short_msg_id") == "7999"

    def test_ignores_error_no_response(self):
        """err_no != 0 responses should not be captured."""
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, response_handlers = _make_pw_mocks()
        err_resp = MagicMock()
        err_resp.status = 200
        err_resp.json.return_value = {"err_no": 403, "err_msg": "forbidden"}

        submit_btn = MagicMock()
        btn_box_locator = MagicMock()
        btn_box_locator.last = submit_btn

        def _click():
            for h in response_handlers:
                h(err_resp)

        submit_btn.click.side_effect = _click

        def _locator(sel):
            if "rich-editor" in sel:
                return MagicMock()
            return submit_btn

        page.locator.side_effect = _locator

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            result = _post_pin_playwright(SAMPLE_COOKIES, "hi")

        assert result == {}

    def test_ignores_json_parse_failure(self):
        """If response.json() raises, the response is silently ignored."""
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, response_handlers = _make_pw_mocks()
        bad_resp = MagicMock()
        bad_resp.status = 200
        bad_resp.json.side_effect = ValueError("not json")

        submit_btn = MagicMock()

        def _click():
            for h in response_handlers:
                h(bad_resp)

        submit_btn.click.side_effect = _click

        def _locator(sel):
            if "rich-editor" in sel:
                return MagicMock()
            return submit_btn

        page.locator.side_effect = _locator

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            result = _post_pin_playwright(SAMPLE_COOKIES, "hi")

        assert result == {}

    def test_only_captures_first_response(self):
        """Second API response must be ignored once data is captured."""
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, response_handlers = _make_pw_mocks()

        resp1 = MagicMock()
        resp1.status = 200
        resp1.json.return_value = {"err_no": 0, "data": {"pin_id": "first"}}
        resp2 = MagicMock()
        resp2.status = 200
        resp2.json.return_value = {"err_no": 0, "data": {"pin_id": "second"}}

        submit_btn = MagicMock()

        def _click():
            for h in response_handlers:
                h(resp1)
                h(resp2)

        submit_btn.click.side_effect = _click

        def _locator(sel):
            if "rich-editor" in sel:
                return MagicMock()
            return submit_btn

        page.locator.side_effect = _locator

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            result = _post_pin_playwright(SAMPLE_COOKIES, "hi")

        assert result.get("pin_id") == "first"

    def test_browser_closed_after_run(self):
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, page, _ = _make_pw_mocks({"pin_id": "7001"})
        pw_instance = fake_pw_mod.sync_playwright.return_value.__enter__.return_value
        browser = pw_instance.chromium.launch.return_value

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            _post_pin_playwright(SAMPLE_COOKIES, "hi")

        browser.close.assert_called_once()

    def test_waits_for_timeout_after_click(self):
        _, page = _run_post_pin({"pin_id": "7001"})
        page.wait_for_timeout.assert_called_once()
        assert page.wait_for_timeout.call_args[0][0] == 3000

    def test_login_flow_when_no_cookies(self):
        """When cookies=None, browser opens login page and saves cookies after input."""
        from fgeo.publishers.juejin_pin import _post_pin_playwright, JUEJIN_LOGIN_URL

        fake_pw_mod, page, _ = _make_pw_mocks({"pin_id": "7001"})
        pw_instance = fake_pw_mod.sync_playwright.return_value.__enter__.return_value
        context = pw_instance.chromium.launch.return_value.new_context.return_value
        context.cookies.return_value = SAMPLE_COOKIES

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("fgeo.publishers.juejin_pin._ensure_data_dir") as mock_ensure, \
             patch("fgeo.publishers.juejin_pin._save_cookies") as mock_save, \
             patch("builtins.input", return_value=""), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            result = _post_pin_playwright(None, "hello no cookies")

        # Login page visited
        first_goto = page.goto.call_args_list[0]
        assert first_goto[0][0] == JUEJIN_LOGIN_URL
        # Cookies saved after login
        mock_ensure.assert_called_once()
        mock_save.assert_called_once_with(SAMPLE_COOKIES)
        # No cookies added to context on init (cookies was None)
        context.add_cookies.assert_not_called()
        assert result.get("pin_id") == "7001"

    def test_always_launches_headed(self):
        """Browser always launches with headless=False, even with valid cookies."""
        from fgeo.publishers.juejin_pin import _post_pin_playwright

        fake_pw_mod, _, _ = _make_pw_mocks({"pin_id": "7001"})
        pw_instance = fake_pw_mod.sync_playwright.return_value.__enter__.return_value

        with patch("fgeo.publishers.juejin_pin._check_playwright"), \
             patch("time.sleep"), \
             patch.dict(sys.modules, {"playwright.sync_api": fake_pw_mod}):
            _post_pin_playwright(SAMPLE_COOKIES, "hi")

        pw_instance.chromium.launch.assert_called_once_with(headless=False)


# ══════════════════════════════════════════════════════════════════════════════
# publish_juejin_pin
# ══════════════════════════════════════════════════════════════════════════════


class TestPublishJuejinPin:
    def test_returns_failed_when_text_too_long(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin, JUEJIN_PIN_MAX_CHARS

        long_text = "x" * (JUEJIN_PIN_MAX_CHARS + 1)
        result = publish_juejin_pin(long_text)
        assert result["status"] == "failed"
        assert "too long" in result["message"]

    def test_returns_failed_when_browser_raises_on_no_cookies(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=None), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", side_effect=RuntimeError("no browser")):
            result = publish_juejin_pin("hello")
        assert result["status"] == "failed"
        assert "Browser error" in result["message"]

    def test_clears_expired_cookies_and_continues(self):
        """Expired cookies are cleared; login is handled inside playwright."""
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=False), \
             patch("fgeo.publishers.juejin_pin._clear_cookies") as mock_clear, \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"pin_id": "ok"}) as mock_post:
            result = publish_juejin_pin("hello")
        mock_clear.assert_called_once()
        mock_post.assert_called_once_with(None, "hello")
        assert result["status"] == "published"

    def test_returns_failed_on_browser_exception(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", side_effect=Exception("crash")):
            result = publish_juejin_pin("hello")
        assert result["status"] == "failed"
        assert "Browser error" in result["message"]
        assert "crash" in result["message"]

    def test_returns_failed_when_no_pin_id(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        # Empty data → no pin ID field
        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={}):
            result = publish_juejin_pin("hello")
        assert result["status"] == "failed"
        assert "No pin ID" in result["message"]

    def test_success_with_pin_id_field(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"pin_id": "7400abc"}):
            result = publish_juejin_pin("hello")
        assert result["status"] == "published"
        assert result["url"] == "https://juejin.cn/pin/7400abc"
        assert result["id"] == "7400abc"
        assert result["message"] == ""

    def test_success_with_short_msg_id_field(self):
        """Juejin 沸点 API primarily returns short_msg_id."""
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"short_msg_id": "7400short"}):
            result = publish_juejin_pin("hello")
        assert result["status"] == "published"
        assert result["id"] == "7400short"
        assert "7400short" in result["url"]

    def test_success_with_generic_id_fallback(self):
        """Any key ending with _id is accepted as fallback."""
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"content_id": "7400cid"}):
            result = publish_juejin_pin("hello")
        assert result["status"] == "published"
        assert result["id"] == "7400cid"

    def test_success_with_msg_id_field(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"msg_id": "7400msg"}):
            result = publish_juejin_pin("hello")
        assert result["status"] == "published"
        assert result["id"] == "7400msg"

    def test_success_with_id_field(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"id": "7400id"}):
            result = publish_juejin_pin("hello")
        assert result["status"] == "published"
        assert result["id"] == "7400id"

    def test_success_at_exact_max_length(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin, JUEJIN_PIN_MAX_CHARS

        text = "x" * JUEJIN_PIN_MAX_CHARS
        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"pin_id": "ok"}):
            result = publish_juejin_pin(text)
        assert result["status"] == "published"

    def test_task_dir_is_ignored(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"pin_id": "ok"}):
            result = publish_juejin_pin("hello", task_dir=Path("/some/path"))
        assert result["status"] == "published"

    def test_pin_url_format(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("fgeo.publishers.juejin_pin._load_cookies", return_value=SAMPLE_COOKIES), \
             patch("fgeo.publishers.juejin_pin._is_logged_in", return_value=True), \
             patch("fgeo.publishers.juejin_pin._post_pin_playwright", return_value={"pin_id": "7123456789012345678"}):
            result = publish_juejin_pin("hello")
        assert result["url"].startswith("https://juejin.cn/pin/")
        assert "7123456789012345678" in result["url"]

