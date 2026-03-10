"""Tests for fgeo/publishers/devto_quickpost.py — DEV.to Quickpost publisher."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


API_KEY = "test-api-key-12345"


def _qp_ok_resp(article_id: int = 9999, path: str = "/testuser/quickpost-title-abc") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"id": article_id, "path": path, "url": f"https://dev.to{path}"}
    resp.raise_for_status.return_value = None
    return resp


def _qp_err_resp() -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"error": "Unprocessable Entity", "status": 422}
    resp.raise_for_status.side_effect = Exception("422 Unprocessable Entity")
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_max_chars(self):
        from fgeo.publishers.devto_quickpost import DEVTO_QP_MAX_CHARS
        assert DEVTO_QP_MAX_CHARS == 256

    def test_api_base(self):
        from fgeo.publishers.devto_quickpost import DEVTO_API_BASE
        assert DEVTO_API_BASE == "https://dev.to/api"


# ══════════════════════════════════════════════════════════════════════════════
# _post_quickpost
# ══════════════════════════════════════════════════════════════════════════════


class TestPostQuickpost:
    def test_posts_to_articles_endpoint(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost, DEVTO_API_BASE

        with patch("httpx.post", return_value=_qp_ok_resp()) as mock_post:
            _post_quickpost("short update", API_KEY)
        url = mock_post.call_args[0][0]
        assert url == f"{DEVTO_API_BASE}/articles"

    def test_api_key_in_header(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost

        with patch("httpx.post", return_value=_qp_ok_resp()) as mock_post:
            _post_quickpost("short update", API_KEY)
        headers = mock_post.call_args[1]["headers"]
        assert headers["api-key"] == API_KEY

    def test_published_true_in_payload(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost

        with patch("httpx.post", return_value=_qp_ok_resp()) as mock_post:
            _post_quickpost("short update", API_KEY)
        payload = mock_post.call_args[1]["json"]
        assert payload["article"]["published"] is True

    def test_body_markdown_is_text(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost

        text = "Hello world update!"
        with patch("httpx.post", return_value=_qp_ok_resp()) as mock_post:
            _post_quickpost(text, API_KEY)
        payload = mock_post.call_args[1]["json"]
        assert payload["article"]["body_markdown"] == text

    def test_title_derived_from_first_line(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost

        text = "First line as title\nSecond line ignored"
        with patch("httpx.post", return_value=_qp_ok_resp()) as mock_post:
            _post_quickpost(text, API_KEY)
        payload = mock_post.call_args[1]["json"]
        assert payload["article"]["title"] == "First line as title"

    def test_title_truncated_to_128_chars(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost

        long_line = "A" * 200
        with patch("httpx.post", return_value=_qp_ok_resp()) as mock_post:
            _post_quickpost(long_line, API_KEY)
        payload = mock_post.call_args[1]["json"]
        assert len(payload["article"]["title"]) <= 128

    def test_empty_text_gives_default_title(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost

        with patch("httpx.post", return_value=_qp_ok_resp()) as mock_post:
            _post_quickpost("", API_KEY)
        payload = mock_post.call_args[1]["json"]
        assert payload["article"]["title"] == "Quickpost"

    def test_raises_runtime_error_when_httpx_missing(self):
        from fgeo.publishers import devto_quickpost

        with patch.dict(sys.modules, {"httpx": None}):
            with pytest.raises(RuntimeError, match="httpx not installed"):
                devto_quickpost._post_quickpost("test", API_KEY)

    def test_calls_raise_for_status(self):
        from fgeo.publishers.devto_quickpost import _post_quickpost

        resp = _qp_ok_resp()
        with patch("httpx.post", return_value=resp):
            _post_quickpost("update", API_KEY)
        resp.raise_for_status.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# publish_devto_quickpost
# ══════════════════════════════════════════════════════════════════════════════


class TestPublishDevtoQuickpost:
    def test_returns_failed_when_httpx_missing(self):
        from fgeo.publishers import devto_quickpost

        with patch.dict(sys.modules, {"httpx": None}):
            result = devto_quickpost.publish_devto_quickpost("hello", api_key=API_KEY)
        assert result["status"] == "failed"
        assert "httpx" in result["message"]

    def test_returns_failed_when_text_too_long(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost, DEVTO_QP_MAX_CHARS

        long_text = "x" * (DEVTO_QP_MAX_CHARS + 1)
        with patch("httpx.post"):  # ensure httpx available
            result = publish_devto_quickpost(long_text, api_key=API_KEY)
        assert result["status"] == "failed"
        assert "too long" in result["message"]

    def test_returns_failed_on_api_exception(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost

        with patch("httpx.post"):
            with patch("fgeo.publishers.devto_quickpost._post_quickpost", side_effect=Exception("network error")):
                result = publish_devto_quickpost("hello", api_key=API_KEY)
        assert result["status"] == "failed"
        assert "network error" in result["message"]

    def test_returns_failed_when_no_article_id(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost

        empty_resp = {"id": 0, "path": ""}
        with patch("httpx.post"):
            with patch("fgeo.publishers.devto_quickpost._post_quickpost", return_value=empty_resp):
                result = publish_devto_quickpost("hello", api_key=API_KEY)
        assert result["status"] == "failed"
        assert "id" in result["message"]

    def test_success_returns_published_url(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost

        article_id = 12345
        path = "/user/my-quickpost-abc"
        ok_resp = {"id": article_id, "path": path}

        with patch("httpx.post"):
            with patch("fgeo.publishers.devto_quickpost._post_quickpost", return_value=ok_resp):
                result = publish_devto_quickpost("Hello world!", api_key=API_KEY)
        assert result["status"] == "published"
        assert result["url"] == f"https://dev.to{path}"
        assert result["id"] == article_id
        assert result["message"] == ""

    def test_success_at_exact_max_length(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost, DEVTO_QP_MAX_CHARS

        text = "x" * DEVTO_QP_MAX_CHARS
        ok_resp = {"id": 1, "path": "/u/p-abc"}

        with patch("httpx.post"):
            with patch("fgeo.publishers.devto_quickpost._post_quickpost", return_value=ok_resp):
                result = publish_devto_quickpost(text, api_key=API_KEY)
        assert result["status"] == "published"

    def test_url_built_from_path_when_present(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost

        ok_resp = {"id": 99, "path": "/mary/hello-world"}
        with patch("httpx.post"):
            with patch("fgeo.publishers.devto_quickpost._post_quickpost", return_value=ok_resp):
                result = publish_devto_quickpost("hello", api_key=API_KEY)
        assert result["url"] == "https://dev.to/mary/hello-world"

    def test_url_empty_when_path_blank(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost

        ok_resp = {"id": 88, "path": ""}
        with patch("httpx.post"):
            with patch("fgeo.publishers.devto_quickpost._post_quickpost", return_value=ok_resp):
                result = publish_devto_quickpost("hello", api_key=API_KEY)
        assert result["url"] == ""

    def test_task_dir_param_accepted(self):
        from fgeo.publishers.devto_quickpost import publish_devto_quickpost

        ok_resp = {"id": 77, "path": "/u/abc"}
        with patch("httpx.post"):
            with patch("fgeo.publishers.devto_quickpost._post_quickpost", return_value=ok_resp):
                result = publish_devto_quickpost("hello", api_key=API_KEY, task_dir=Path("/tmp"))
        assert result["status"] == "published"
