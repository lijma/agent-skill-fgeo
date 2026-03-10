"""Tests for fgeo/publishers/juejin_pin.py — 掘金沸点 publisher."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SAMPLE_COOKIES = [
    {"name": "sessionid", "value": "abc123", "domain": ".juejin.cn"},
    {"name": "uid_tt", "value": "xyz", "domain": ".juejin.cn"},
]


def _pin_ok_resp(pin_id: str = "7400000000000000001") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"err_no": 0, "data": {"pin_id": pin_id}}
    resp.raise_for_status.return_value = None
    return resp


def _pin_err_resp() -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"err_no": 403, "err_msg": "rate limit"}
    resp.raise_for_status.return_value = None
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_max_chars(self):
        from fgeo.publishers.juejin_pin import JUEJIN_PIN_MAX_CHARS
        assert JUEJIN_PIN_MAX_CHARS == 1000

    def test_api_url(self):
        from fgeo.publishers.juejin_pin import JUEJIN_PIN_API_URL
        assert "euler" in JUEJIN_PIN_API_URL
        assert "pin/create" in JUEJIN_PIN_API_URL
        assert "api.juejin.cn" in JUEJIN_PIN_API_URL


# ══════════════════════════════════════════════════════════════════════════════
# _post_pin
# ══════════════════════════════════════════════════════════════════════════════


class TestPostPin:
    def test_posts_to_correct_url(self):
        from fgeo.publishers.juejin_pin import _post_pin, JUEJIN_PIN_API_URL, JUEJIN_AID

        with patch("httpx.post", return_value=_pin_ok_resp()) as mock_post:
            _post_pin(SAMPLE_COOKIES, "Hello pin!")
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == JUEJIN_PIN_API_URL
        assert call_kwargs[1]["params"]["aid"] == JUEJIN_AID

    def test_payload_contains_content(self):
        from fgeo.publishers.juejin_pin import _post_pin

        with patch("httpx.post", return_value=_pin_ok_resp()) as mock_post:
            _post_pin(SAMPLE_COOKIES, "My pin content")
        payload = mock_post.call_args[1]["json"]
        assert payload["content"] == "My pin content"

    def test_payload_has_empty_topic_ids_by_default(self):
        from fgeo.publishers.juejin_pin import _post_pin

        with patch("httpx.post", return_value=_pin_ok_resp()) as mock_post:
            _post_pin(SAMPLE_COOKIES, "test")
        payload = mock_post.call_args[1]["json"]
        assert payload["topic_ids"] == []

    def test_payload_allows_custom_topic_ids(self):
        from fgeo.publishers.juejin_pin import _post_pin

        with patch("httpx.post", return_value=_pin_ok_resp()) as mock_post:
            _post_pin(SAMPLE_COOKIES, "test", topic_ids=["123"])
        payload = mock_post.call_args[1]["json"]
        assert payload["topic_ids"] == ["123"]

    def test_cookie_header_sent(self):
        from fgeo.publishers.juejin_pin import _post_pin

        with patch("httpx.post", return_value=_pin_ok_resp()) as mock_post:
            _post_pin(SAMPLE_COOKIES, "test")
        headers = mock_post.call_args[1]["headers"]
        assert "Cookie" in headers
        assert "sessionid=abc123" in headers["Cookie"]

    def test_raises_runtime_error_when_httpx_missing(self):
        from fgeo.publishers import juejin_pin

        with patch.dict(sys.modules, {"httpx": None}):
            with pytest.raises(RuntimeError, match="httpx not installed"):
                juejin_pin._post_pin(SAMPLE_COOKIES, "test")

    def test_calls_raise_for_status(self):
        from fgeo.publishers.juejin_pin import _post_pin

        resp = _pin_ok_resp()
        with patch("httpx.post", return_value=resp):
            _post_pin(SAMPLE_COOKIES, "test")
        resp.raise_for_status.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# publish_juejin_pin
# ══════════════════════════════════════════════════════════════════════════════


class TestPublishJuejinPin:
    def test_returns_failed_when_httpx_missing(self):
        from fgeo.publishers import juejin_pin

        with patch.dict(sys.modules, {"httpx": None}):
            result = juejin_pin.publish_juejin_pin("hello")
        assert result["status"] == "failed"
        assert "httpx" in result["message"]

    def test_returns_failed_when_text_too_long(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin, JUEJIN_PIN_MAX_CHARS

        long_text = "x" * (JUEJIN_PIN_MAX_CHARS + 1)
        with patch("httpx.post"):  # ensure httpx is available
            result = publish_juejin_pin(long_text)
        assert result["status"] == "failed"
        assert "too long" in result["message"]

    def test_returns_failed_when_login_fails(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("httpx.post"):
            with patch("fgeo.publishers.juejin_pin._get_cookies", return_value=None):
                result = publish_juejin_pin("hello")
        assert result["status"] == "failed"
        assert "Login" in result["message"] or "cookies" in result["message"]

    def test_returns_failed_on_api_exception(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("httpx.post"):
            with patch("fgeo.publishers.juejin_pin._get_cookies", return_value=SAMPLE_COOKIES):
                with patch("fgeo.publishers.juejin_pin._post_pin", side_effect=Exception("timeout")):
                    result = publish_juejin_pin("hello")
        assert result["status"] == "failed"
        assert "timeout" in result["message"]

    def test_returns_failed_on_api_error_no(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        with patch("httpx.post"):
            with patch("fgeo.publishers.juejin_pin._get_cookies", return_value=SAMPLE_COOKIES):
                with patch("fgeo.publishers.juejin_pin._post_pin", return_value=_pin_err_resp().json.return_value):
                    result = publish_juejin_pin("hello")
        assert result["status"] == "failed"

    def test_returns_failed_when_no_pin_id(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        empty_resp = {"err_no": 0, "data": {}}
        with patch("httpx.post"):
            with patch("fgeo.publishers.juejin_pin._get_cookies", return_value=SAMPLE_COOKIES):
                with patch("fgeo.publishers.juejin_pin._post_pin", return_value=empty_resp):
                    result = publish_juejin_pin("hello")
        assert result["status"] == "failed"
        assert "pin_id" in result["message"]

    def test_success_returns_pin_url(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        pin_id = "7400000000000000001"
        ok_resp = {"err_no": 0, "data": {"pin_id": pin_id}}

        with patch("httpx.post"):
            with patch("fgeo.publishers.juejin_pin._get_cookies", return_value=SAMPLE_COOKIES):
                with patch("fgeo.publishers.juejin_pin._post_pin", return_value=ok_resp):
                    result = publish_juejin_pin("hello")
        assert result["status"] == "published"
        assert result["url"] == f"https://juejin.cn/pin/{pin_id}"
        assert result["id"] == pin_id
        assert result["message"] == ""

    def test_success_at_exact_max_length(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin, JUEJIN_PIN_MAX_CHARS

        text = "x" * JUEJIN_PIN_MAX_CHARS
        ok_resp = {"err_no": 0, "data": {"pin_id": "9999"}}

        with patch("httpx.post"):
            with patch("fgeo.publishers.juejin_pin._get_cookies", return_value=SAMPLE_COOKIES):
                with patch("fgeo.publishers.juejin_pin._post_pin", return_value=ok_resp):
                    result = publish_juejin_pin(text)
        assert result["status"] == "published"

    def test_task_dir_param_accepted(self):
        from fgeo.publishers.juejin_pin import publish_juejin_pin

        ok_resp = {"err_no": 0, "data": {"pin_id": "1234"}}
        with patch("httpx.post"):
            with patch("fgeo.publishers.juejin_pin._get_cookies", return_value=SAMPLE_COOKIES):
                with patch("fgeo.publishers.juejin_pin._post_pin", return_value=ok_resp):
                    result = publish_juejin_pin("hello", task_dir=Path("/tmp"))
        assert result["status"] == "published"
