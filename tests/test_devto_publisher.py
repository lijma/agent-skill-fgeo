"""Tests for DEV.to publisher (fgeo.publishers.devto)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── _strip_frontmatter ────────────────────────────────────────────────────────

class TestStripFrontmatter:
    def test_strips_yaml_and_returns_body(self):
        from fgeo.publishers.devto import _strip_frontmatter
        md = "---\ntitle: Hello\ntags: python\n---\nBody text"
        fm, body = _strip_frontmatter(md)
        assert fm["title"] == "Hello"
        assert fm["tags"] == "python"
        assert body == "Body text"

    def test_no_frontmatter_returns_empty_dict(self):
        from fgeo.publishers.devto import _strip_frontmatter
        fm, body = _strip_frontmatter("Just a body")
        assert fm == {}
        assert body == "Just a body"

    def test_canonical_url_parsed(self):
        from fgeo.publishers.devto import _strip_frontmatter
        md = "---\ncanonical_url: https://example.com/post\n---\nBody"
        fm, _ = _strip_frontmatter(md)
        assert fm["canonical_url"] == "https://example.com/post"


# ── _build_devto_body ─────────────────────────────────────────────────────────

class TestBuildDevtoBody:
    def test_uses_frontmatter_title_over_param(self):
        from fgeo.publishers.devto import _build_devto_body
        md = "---\ntitle: FM Title\n---\nBody"
        payload = _build_devto_body("Param Title", md, [], "")
        assert payload["title"] == "FM Title"

    def test_falls_back_to_param_title_if_no_fm(self):
        from fgeo.publishers.devto import _build_devto_body
        payload = _build_devto_body("My Title", "No frontmatter", [], "")
        assert payload["title"] == "My Title"

    def test_always_draft(self):
        from fgeo.publishers.devto import _build_devto_body
        payload = _build_devto_body("T", "Body", [], "")
        assert payload["published"] is False

    def test_merges_tags_max_4(self):
        from fgeo.publishers.devto import _build_devto_body
        md = "---\ntags: python, devops\n---\nBody"
        payload = _build_devto_body("T", md, ["fgeo", "cli", "extra"], "")
        assert len(payload["tags"]) <= 4

    def test_deduplicates_tags(self):
        from fgeo.publishers.devto import _build_devto_body
        md = "---\ntags: python\n---\nBody"
        payload = _build_devto_body("T", md, ["python", "cli"], "")
        assert payload["tags"].count("python") == 1

    def test_canonical_url_included(self):
        from fgeo.publishers.devto import _build_devto_body
        md = "---\ncanonical_url: https://myblog.com/post\n---\nBody"
        payload = _build_devto_body("T", md, [], "")
        assert payload["canonical_url"] == "https://myblog.com/post"

    def test_series_included_when_set(self):
        from fgeo.publishers.devto import _build_devto_body
        payload = _build_devto_body("T", "Body", [], "My Series")
        assert payload["series"] == "My Series"

    def test_series_omitted_when_empty(self):
        from fgeo.publishers.devto import _build_devto_body
        payload = _build_devto_body("T", "Body", [], "")
        assert "series" not in payload

    def test_description_from_frontmatter(self):
        from fgeo.publishers.devto import _build_devto_body
        md = "---\ndescription: A short desc\n---\nBody"
        payload = _build_devto_body("T", md, [], "")
        assert payload["description"] == "A short desc"


# ── publish_to_devto ──────────────────────────────────────────────────────────

class TestPublishToDevto:
    def _make_response(self, status_code: int, data: dict) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = data
        resp.text = str(data)
        return resp

    def test_success_returns_draft_saved(self):
        from fgeo.publishers.devto import publish_to_devto
        resp = self._make_response(201, {"id": 42, "url": "https://dev.to/user/article-abc"})
        with patch("httpx.post", return_value=resp):
            result = publish_to_devto("Title", "Body", api_key="key123")
        assert result["status"] == "draft_saved"
        assert result["url"] == "https://dev.to/user/article-abc"
        assert result["id"] == 42

    def test_api_error_returns_failed(self):
        from fgeo.publishers.devto import publish_to_devto
        resp = self._make_response(422, {"error": "unprocessable"})
        with patch("httpx.post", return_value=resp):
            result = publish_to_devto("Title", "Body", api_key="bad")
        assert result["status"] == "failed"
        assert "422" in result["message"]

    def test_network_error_returns_failed(self):
        from fgeo.publishers.devto import publish_to_devto
        with patch("httpx.post", side_effect=Exception("Connection refused")):
            result = publish_to_devto("Title", "Body", api_key="key")
        assert result["status"] == "failed"
        assert "Connection refused" in result["message"]

    def test_missing_httpx_returns_failed(self):
        from fgeo.publishers.devto import publish_to_devto
        import sys
        with patch.dict(sys.modules, {"httpx": None}):
            result = publish_to_devto("Title", "Body", api_key="key")
        assert result["status"] == "failed"
        assert "httpx" in result["message"]

    def test_passes_api_key_header(self):
        from fgeo.publishers.devto import publish_to_devto
        resp = self._make_response(201, {"id": 1, "url": "https://dev.to/u/a"})
        with patch("httpx.post", return_value=resp) as mock_post:
            publish_to_devto("T", "Body", api_key="my-secret-key")
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["headers"]["api-key"] == "my-secret-key"

    def test_tags_passed_in_payload(self):
        from fgeo.publishers.devto import publish_to_devto
        resp = self._make_response(201, {"id": 1, "url": "https://dev.to/u/a"})
        with patch("httpx.post", return_value=resp) as mock_post:
            publish_to_devto("T", "Body", api_key="k", tags=["python", "fgeo"])
        payload = mock_post.call_args.kwargs["json"]["article"]
        assert "python" in payload["tags"]
        assert "fgeo" in payload["tags"]
