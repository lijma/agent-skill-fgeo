"""DEV.to publisher via Forem REST API.

Publishes a Markdown article to DEV.to as a draft using the official Forem API:
  POST https://dev.to/api/articles
  Header: api-key: <API_KEY>

The article is always created as a **draft** first so the user can review it on
DEV.to before publishing.  After the user publishes manually on DEV.to, run:
  fgeo publish task done <task_id>

DEV.to API key:
  Sign in → Settings → Extensions → DEV Community API Keys → Generate
  https://dev.to/settings/extensions

Usage::

    from fgeo.publishers.devto import publish_to_devto

    result = publish_to_devto(
        title="My Article",
        markdown_content="# Hello\\n\\nBody ...",
        tags=["python", "devops"],
        series="My Series",
    )
    # result = {"status": "draft_saved", "url": "https://dev.to/...", "id": 12345}
"""

from __future__ import annotations

import re
from typing import Any

from rich.console import Console

console = Console()

DEVTO_API_BASE = "https://dev.to/api"


def _strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split YAML frontmatter from body.  Returns (frontmatter_dict, body)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:  # pragma: no cover
        return {}, text
    fm_raw, body = parts[1], parts[2].lstrip("\n")
    fm: dict[str, str] = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def _build_devto_body(title: str, markdown: str, tags: list[str], series: str) -> dict[str, Any]:
    """Build the JSON payload for the DEV.to article creation endpoint."""
    fm, body = _strip_frontmatter(markdown)

    # Merge tags from frontmatter (comma or space separated) and explicit param
    fm_tags_raw = fm.get("tags", "")
    fm_tags = [t.strip().lower() for t in re.split(r"[,\s]+", fm_tags_raw) if t.strip()]
    merged_tags = list(dict.fromkeys(fm_tags + [t.lower() for t in tags]))[:4]  # DEV.to limit: 4

    article: dict[str, Any] = {
        "title": fm.get("title", title),
        "body_markdown": body,
        "published": False,  # always draft first
        "tags": merged_tags,
    }
    if series or fm.get("series"):
        article["series"] = series or fm.get("series", "")
    if fm.get("canonical_url"):
        article["canonical_url"] = fm["canonical_url"]
    if fm.get("description"):
        article["description"] = fm["description"]
    return article


def publish_to_devto(
    title: str,
    markdown_content: str,
    api_key: str,
    tags: list[str] | None = None,
    series: str = "",
) -> dict[str, Any]:
    """Create a DEV.to draft via the Forem REST API.

    Args:
        title: Article title (used if frontmatter has no title).
        markdown_content: Raw Markdown content (may include YAML frontmatter).
        api_key: DEV.to API key (from Settings → Extensions).
        tags: Optional list of tags (max 4, merged with frontmatter tags).
        series: Optional series / collection name.

    Returns:
        dict with keys: status, url, id, message
        status is one of: draft_saved | failed
    """
    try:
        import httpx  # noqa: PLC0415
    except ImportError:
        console.print(  # pragma: no cover
            "[red]httpx not installed.[/red]\n"
            "Run: [bold]pip install fgeo[publish][/bold]"
        )
        return {"status": "failed", "url": "", "id": 0, "message": "httpx not installed"}

    payload = _build_devto_body(title, markdown_content, tags or [], series)

    console.print("[dim]Posting draft to DEV.to…[/dim]")
    try:
        resp = httpx.post(
            f"{DEVTO_API_BASE}/articles",
            json={"article": payload},
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/vnd.forem.api-v1+json",
            },
            timeout=30,
        )
    except Exception as exc:
        return {"status": "failed", "url": "", "id": 0, "message": str(exc)}

    if resp.status_code not in (200, 201):
        msg = f"HTTP {resp.status_code}: {resp.text[:300]}"
        console.print(f"[red]DEV.to API error:[/red] {msg}")
        return {"status": "failed", "url": "", "id": 0, "message": msg}

    data = resp.json()
    article_id = data.get("id", 0)
    url = data.get("url", "") or f"https://dev.to/dashboard"

    console.print(f"[green]Draft created on DEV.to:[/green] {url}")
    return {"status": "draft_saved", "url": url, "id": article_id, "message": ""}
