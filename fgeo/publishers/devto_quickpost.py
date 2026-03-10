"""DEV.to Quickpost publisher — short-form posts via Forem REST API.

Publishes a short text post directly to DEV.to (immediately published, not a
draft).  The 256-character limit mirrors the DEV.to Quickpost UI limit.

Uses the same API key as the full article publisher (fgeo platform_secret field
on the devto-quickpost platform).

API used:
  POST https://dev.to/api/articles
  Header: api-key: <API_KEY>
  Body: {"article": {"title": "...", "body_markdown": "...", "published": true}}

The post is published immediately — no draft / task cycle needed.

Usage::

    from fgeo.publishers.devto_quickpost import publish_devto_quickpost

    result = publish_devto_quickpost("Short update text.", api_key="xxx")
    # result = {"status": "published" | "failed", "url": "https://dev.to/...",
    #           "id": 12345, "message": ""}
"""

from __future__ import annotations

from typing import Any

from rich.console import Console

console = Console()

DEVTO_API_BASE = "https://dev.to/api"
DEVTO_QP_MAX_CHARS = 256


def _post_quickpost(text: str, api_key: str) -> dict[str, Any]:
    """POST a quickpost to the DEV.to Forem API.

    The post is published immediately (``published: true``).  The title is
    derived from the first line of the text (truncated to 128 chars).

    Raises:
        RuntimeError: if httpx is not installed.
    """
    try:
        import httpx  # noqa: PLC0415
    except ImportError as err:
        raise RuntimeError("httpx not installed — run: pip install httpx") from err

    # Use the first line or first 80 chars as the title
    first_line = text.splitlines()[0].strip() if text.strip() else "Quickpost"
    title = first_line[:128] if first_line else "Quickpost"

    payload: dict[str, Any] = {
        "article": {
            "title": title,
            "body_markdown": text,
            "published": True,
        }
    }
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/vnd.forem.api-v1+json",
    }
    response = httpx.post(
        f"{DEVTO_API_BASE}/articles",
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def publish_devto_quickpost(
    text: str,
    api_key: str,
    task_dir=None,
) -> dict[str, Any]:
    """Publish a quickpost to DEV.to immediately (no draft review step).

    Args:
        text: Post content (max 256 characters).
        api_key: DEV.to API key (from Settings → Extensions → Generate API Key).
        task_dir: Unused — reserved for future logging.

    Returns:
        dict with keys:
            status  : "published" | "failed"
            url     : post URL (empty on failure)
            id      : article id (0 on failure)
            message : error message (empty on success)
    """
    # ── Dependency check ──────────────────────────────────────────────────────
    try:
        import httpx  # noqa: F401, PLC0415
    except ImportError:
        return {
            "status": "failed",
            "url": "",
            "id": 0,
            "message": "httpx not installed — run: pip install httpx",
        }

    # ── Length validation ─────────────────────────────────────────────────────
    if len(text) > DEVTO_QP_MAX_CHARS:
        return {
            "status": "failed",
            "url": "",
            "id": 0,
            "message": (
                f"Content too long: {len(text)} chars "
                f"(max {DEVTO_QP_MAX_CHARS})"
            ),
        }

    # ── API call ──────────────────────────────────────────────────────────────
    try:
        resp = _post_quickpost(text, api_key)
    except Exception as exc:
        return {
            "status": "failed",
            "url": "",
            "id": 0,
            "message": f"API error: {exc}",
        }

    article_id = resp.get("id", 0)
    path = resp.get("path", "")
    url = f"https://dev.to{path}" if path else ""

    if not article_id:
        return {
            "status": "failed",
            "url": "",
            "id": 0,
            "message": "DEV.to API returned no article id",
        }

    console.print(f"[dim]DEV.to quickpost published: {url}[/dim]")
    return {
        "status": "published",
        "url": url,
        "id": article_id,
        "message": "",
    }
