"""fgeo publish — Publish content to platforms."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fgeo.constants import FGEO_HOME
from fgeo.database import get_db

console = Console()
publish_app = typer.Typer(help="Publish content to platforms.")
task_app = typer.Typer(help="Manage publish tasks (git PR workflow).")
publish_app.add_typer(task_app, name="task")

# Platform names with built-in publishing support
BLOG_PLATFORM = "blog"
BSKY_PLATFORM = "bluesky"
WECHAT_PLATFORM = "公众号"
MEDIUM_PLATFORM = "medium"
DEVTO_PLATFORM = "devto"
JUEJIN_PLATFORM = "掘金"
JUEJIN_PLATFORM_ALT = "juejin"
JUEJIN_PIN_PLATFORM = "掘金沸点"
JUEJIN_PIN_PLATFORM_ALT = "juejin-pin"
DEVTO_QP_PLATFORM = "devto-quickpost"

# Bluesky hard limit: 300 graphemes per post.
# We use 295 as a safe margin. Content exceeding this is rejected at publish time.
BSKY_MAX_GRAPHEMES = 295

# 掘金沸点 pin character limit (Unicode chars, not graphemes)
JUEJIN_PIN_MAX_CHARS = 1000

# DEV.to Quickpost character limit (Unicode chars, mirrors the UI counter)
DEVTO_QP_MAX_CHARS = 256


# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def _with_date_prefix(filename: str) -> str:
    """Add YYYY-MM-DD- prefix if not already present."""
    if re.match(r"^\d{4}-\d{2}-\d{2}-", filename):
        return filename
    return f"{_date_prefix()}-{filename}"


def _resolve_platform_row(db, platform_id: str | None) -> dict:
    """Return the full platform row (name, publish_url, …) or empty dict."""
    if not platform_id:
        return {}
    row = db.conn.execute("SELECT * FROM platforms WHERE id=?", (platform_id,)).fetchone()
    return dict(row) if row else {}


def _run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def _make_task_id(content_id: str) -> str:
    h = hashlib.sha256(f"{content_id}-{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    return f"ptask-{h}"


def _git_remote_to_web_url(remote: str) -> str:
    """Convert a git remote URL to its GitHub web base URL.

    git@github.com:user/repo.git  →  https://github.com/user/repo
    https://github.com/user/repo.git  →  https://github.com/user/repo
    """
    remote = remote.strip()
    m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", remote)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    if remote.endswith(".git"):
        return remote[:-4]
    return remote


# ── Bluesky flow ──────────────────────────────────────────────────────────────

def _strip_md(text: str) -> str:
    """Strip common Markdown formatting from text."""
    text = re.sub(r"#+ ", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"<!-- more -->", "", text)
    return text


# Required DEV.to-style frontmatter fields that every article should declare.
_REQUIRED_FM_FIELDS = ("title", "description", "tags")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter block from Markdown text.

    Returns:
        (fields, body) where ``fields`` is a dict of key→value strings and
        ``body`` is the Markdown content after the closing ``---`` delimiter.
        Both are empty / equal to ``text`` when no frontmatter is present.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fields: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip().strip("\"'")
    return fields, parts[2]


def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter (--- ... ---) from text."""
    _, body = _parse_frontmatter(text)
    return body


_FM_WARN_PREFIX = "[yellow]⚠  Frontmatter:[/yellow]"


def _check_devto_frontmatter(src: Path) -> None:
    """Warn if the source file is missing recommended DEV.to frontmatter fields.

    The DEV.to frontmatter block (title / description / tags / …) serves as the
    canonical metadata record for every article.  Other platforms strip it before
    uploading; DEV.to keeps it verbatim.  This check is non-blocking — publishing
    continues even when fields are absent.
    """
    try:
        text = src.read_text(encoding="utf-8")
    except OSError:
        return

    if not text.startswith("---"):
        console.print(
            f"{_FM_WARN_PREFIX} {src.name} has no frontmatter block.\n"
            "  Add a block like:\n"
            "    ---\n"
            "    title: \"…\"\n"
            "    description: \"…\"\n"
            "    tags: ai, dev\n"
            "    ---"
        )
        return

    fields, _ = _parse_frontmatter(text)
    missing = [f for f in _REQUIRED_FM_FIELDS if not fields.get(f)]
    if missing:
        console.print(
            f"{_FM_WARN_PREFIX} {src.name} is missing: "
            + ", ".join(f'[bold]{f}[/bold]' for f in missing)
        )


def _extract_bsky_text(src: Path, max_chars: int = 270) -> str:
    """Extract a clean text snippet from a Markdown article for Bluesky posting.

    Strips YAML frontmatter and Markdown formatting. Prefers the '太长不读' paragraph.
    Used when cross-posting a long-form article to Bluesky (snippet-only mode).
    """
    text = src.read_text(encoding="utf-8")
    text = _strip_frontmatter(text)

    # Try to find a TLDR block (太长不读)
    tldr_match = re.search(r"\*\*太长不读\*\*[：:](.*?)(?:\n\n|\Z)", text, re.DOTALL)
    if tldr_match:
        snippet = tldr_match.group(0)
    else:
        # Fall back to first non-empty paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        snippet = paragraphs[0] if paragraphs else text

    snippet = _strip_md(snippet)
    snippet = " ".join(snippet.split())  # normalise whitespace
    return snippet[:max_chars].rstrip()


def _graphemes(text: str) -> int:
    """Count grapheme clusters (approximated as Unicode codepoints for BMP text).

    Bluesky's 300-grapheme limit rarely involves multi-codepoint graphemes for
    typical Latin/CJK content, so len() is a safe approximation.
    """
    return len(text)


def _split_bsky_thread(src: Path, max_graphemes: int = 295, max_paras: int = 2) -> list[str]:
    """Split Markdown content into Bluesky posts respecting grapheme and paragraph limits.

    Rules (per Bluesky style guide):
    - Each post ≤ max_graphemes graphemes (Bluesky hard limit is 300)
    - Each post contains at most max_paras paragraphs (default 2)
    - Paragraphs are greedily merged within both limits
    - Long single paragraphs are split by sentence boundaries
    """
    text = src.read_text(encoding="utf-8")
    text = _strip_frontmatter(text)
    text = _strip_md(text)

    paragraphs = [" ".join(p.split()) for p in text.split("\n\n") if p.strip()]

    # Expand paragraphs that are too long into sentence-level chunks
    chunks: list[str] = []
    for para in paragraphs:
        if _graphemes(para) <= max_graphemes:
            chunks.append(para)
        else:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current = ""
            for sentence in sentences:
                candidate = (current + " " + sentence).strip() if current else sentence
                if _graphemes(candidate) <= max_graphemes:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = sentence[:max_graphemes].rstrip()
            if current:
                chunks.append(current)

    # Greedy merge: keep adding chunks to current post while limits allow
    posts: list[str] = []
    current_post = ""
    current_para_count = 0
    for chunk in chunks:
        separator = "\n\n" if current_post else ""
        candidate = current_post + separator + chunk
        if current_post and (
            _graphemes(candidate) > max_graphemes or current_para_count >= max_paras
        ):
            posts.append(current_post)
            current_post = chunk
            current_para_count = 1
        else:
            current_post = candidate
            current_para_count += 1
    if current_post:
        posts.append(current_post)

    return posts if posts else ["(empty)"]


def _build_facets(text: str, bsky_models) -> list:  # noqa: ANN001
    """Build Bluesky rich-text facets for URLs and hashtags found in text.

    Facet byte offsets use UTF-8 encoding as required by the AT Protocol.
    Supports:
    - app.bsky.richtext.facet#link  — for https?:// URLs
    - app.bsky.richtext.facet#tag   — for #hashtags
    """
    facets = []

    def _byte_offsets(match_start: int, match_end: int) -> tuple[int, int]:
        return (
            len(text[:match_start].encode("utf-8")),
            len(text[:match_end].encode("utf-8")),
        )

    # URLs
    for m in re.finditer(r"https?://[^\s>\)\]]+", text):
        url = m.group(0).rstrip(".,;!?")
        byte_start, byte_end = _byte_offsets(m.start(), m.start() + len(url))
        facets.append(
            bsky_models.AppBskyRichtextFacet.Main(
                index=bsky_models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=byte_start, byte_end=byte_end
                ),
                features=[bsky_models.AppBskyRichtextFacet.Link(uri=url)],
            )
        )

    # Hashtags
    for m in re.finditer(r"(?:^|\s)(#[^\d\s]\S*)", text):
        tag_with_hash = m.group(1).rstrip(".,;!?")
        tag = tag_with_hash.lstrip("#")
        if not tag or len(tag_with_hash) >= 66:
            continue
        start = m.start(1)
        end = start + len(tag_with_hash)
        byte_start, byte_end = _byte_offsets(start, end)
        facets.append(
            bsky_models.AppBskyRichtextFacet.Main(
                index=bsky_models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=byte_start, byte_end=byte_end
                ),
                features=[bsky_models.AppBskyRichtextFacet.Tag(tag=tag)],
            )
        )

    return facets


def _publish_bsky(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    bsky_handle: str,
    app_password: str,
    now_iso: str,
) -> None:
    """Post content to Bluesky via AT Protocol and create a publish task."""
    try:
        from atproto import Client  # noqa: PLC0415
        from atproto import models as bsky_models  # noqa: PLC0415
    except ImportError:
        console.print("[red]atproto not installed.[/red] Run: [bold]pip install atproto[/bold]")
        raise typer.Exit(1)

    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Build the post text (strip frontmatter + Markdown)
    raw = src.read_text(encoding="utf-8")
    post_text = _strip_md(_strip_frontmatter(raw)).strip()
    # Collapse excessive blank lines but keep paragraph breaks
    post_text = re.sub(r"\n{3,}", "\n\n", post_text).strip()

    # ── Length validation ────────────────────────────────────────────────────
    total_graphemes = _graphemes(post_text)
    if total_graphemes > BSKY_MAX_GRAPHEMES:
        console.print(
            f"[red]✗ Content too long for Bluesky[/red]\n"
            f"  Current length : [bold]{total_graphemes}[/bold] graphemes\n"
            f"  Limit          : [bold]{BSKY_MAX_GRAPHEMES}[/bold] graphemes\n\n"
            f"Bluesky is like 朋友圈 — keep it short and punchy.\n"
            f"Please trim your content and try again."
        )
        raise typer.Exit(1)
    # ─────────────────────────────────────────────────────────────────────────


    client = Client()
    console.print(f"[dim]Logging in to Bluesky as {bsky_handle} …[/dim]")
    try:
        client.login(bsky_handle, app_password)
    except Exception as exc:
        console.print(f"[red]Bluesky login failed:[/red] {exc}")
        raise typer.Exit(1)

    # Build external link embed from the first URL found in the post text.
    # Previously this used content["published_url"], which could be wrong
    # (e.g. a previous bsky post URL), causing the embed to link to itself.
    embed = None
    url_match = re.search(r"https?://[^\s>\)\]]+", post_text)
    if url_match:
        embed_url = url_match.group(0).rstrip(".,;!?")
        # Build description from text AFTER the URL (or before), excluding the URL itself
        embed_desc = re.sub(r"https?://[^\s>\)\]]+", "", post_text).strip()
        embed_desc = " ".join(embed_desc.split())[:200]
        embed = bsky_models.AppBskyEmbedExternal.Main(
            external=bsky_models.AppBskyEmbedExternal.External(
                uri=embed_url,
                title=title,
                description=embed_desc,
            )
        )

    console.print("[dim]Sending post …[/dim]")
    try:
        facets = _build_facets(post_text, bsky_models) or None
        response = client.send_post(text=post_text, facets=facets, embed=embed)
        post_uri = response.uri
    except Exception as exc:
        console.print(f"[red]Post failed:[/red] {exc}")
        raise typer.Exit(1)

    # Convert AT URI → bsky.app URL: at://did:plc:xxx/app.bsky.feed.post/rkey → URL
    post_url = ""
    parts = post_uri.split("/")
    if len(parts) >= 5:
        rkey = parts[-1]
        post_url = f"https://bsky.app/profile/{bsky_handle}/post/{rkey}"

    platform_id = content.get("platform_id") or ""
    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=platform_id,
        repo_url=f"https://bsky.app/profile/{bsky_handle}",
        branch="",
        task_dir=str(task_dir),
        pr_url=post_url or post_uri,
        status="pr_open",
    )
    db.update_content(content_id, "status", "published")
    db.update_content(content_id, "published_at", now_iso)
    if post_url:
        db.update_content(content_id, "published_url", post_url)

    body = (
        f"[bold]Post URL:[/bold]  {post_url or post_uri}\n"
        f"[bold]Task ID:[/bold]   {task_id}\n"
        f"\nRun [bold]fgeo publish task done {task_id}[/bold] to confirm."
    )
    console.print(Panel(body, title=f"[green]✓ Posted to Bluesky[/green] — {title}"))


# ── Medium RPA flow ──────────────────────────────────────────────────────────

def _publish_medium(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    now_iso: str,
) -> None:
    """Publish a Markdown article to Medium as a draft via Playwright RPA.

    Flow:
    1. Launch Playwright (headed if login needed, cookied if session cached).
    2. Navigate to medium.com/new-story editor.
    3. Fill title (h3.graf--title) and paste HTML body via ClipboardEvent.
    4. Wait for Medium auto-save → capture draft URL.
    5. Create a ``pr_open`` publish task (user manually reviews and publishes on Medium,
       then runs ``fgeo publish task done <task_id>``).
    """
    from fgeo.publishers.medium import publish_to_medium  # noqa: PLC0415

    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    raw_markdown = src.read_text(encoding="utf-8")
    fm_fields, markdown_content = _parse_frontmatter(raw_markdown)

    # Pull subtitle + tags: prefer frontmatter values, fall back to content record
    subtitle = fm_fields.get("description") or content.get("description") or ""
    raw_tags = fm_fields.get("tags") or content.get("tags") or ""
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    console.print("[bold]Publishing to Medium via browser …[/bold]")
    result = publish_to_medium(
        title=title,
        markdown_content=markdown_content,
        subtitle=subtitle,
        tags=tags,
        task_dir=task_dir,
    )

    platform_id = content.get("platform_id") or ""
    draft_url = result.get("url", "")

    status = result.get("status", "")

    if status == "failed":
        console.print(f"[red]Medium publish failed:[/red] {result.get('message', 'unknown error')}")
        db.create_publish_task(
            task_id=task_id,
            content_id=content_id,
            platform_id=platform_id,
            repo_url="https://medium.com",
            branch="",
            task_dir=str(task_dir),
            pr_url="",
            status="failed",
        )
        raise typer.Exit(1)

    if status == "published":
        # Article is live — mark task as merged and content as published
        db.create_publish_task(
            task_id=task_id,
            content_id=content_id,
            platform_id=platform_id,
            repo_url="https://medium.com",
            branch="",
            task_dir=str(task_dir),
            pr_url=draft_url,
            status="merged",
        )
        if draft_url:
            db.update_content(content_id, "published_url", draft_url)
        db.update_content(content_id, "status", "published")
        body = (
            f"[bold]Task ID:[/bold]   {task_id}\n"
            f"[bold]Status:[/bold]    published\n"
        )
        if draft_url:
            body += f"[bold]URL:[/bold]       {draft_url}\n"
        console.print(Panel(body, title=f"[green]✓ Published to Medium[/green] — {title}"))
        return

    # draft_saved — auto-publish failed, user must publish manually
    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=platform_id,
        repo_url="https://medium.com",
        branch="",
        task_dir=str(task_dir),
        pr_url=draft_url,
        status="pr_open",
    )
    if draft_url:
        db.update_content(content_id, "published_url", draft_url)

    body = (
        f"[bold]Task ID:[/bold]   {task_id}\n"
        f"[bold]Status:[/bold]    draft (auto-publish failed — review and publish manually)\n"
    )
    if draft_url:
        body += f"[bold]Draft URL:[/bold] {draft_url}\n"
    body += (
        "\nOpen the link above in your browser to publish.\n"
        f"After publishing, run: [bold]fgeo publish task done {task_id}[/bold]"
    )
    console.print(Panel(body, title=f"[yellow]⚠ Draft saved to Medium[/yellow] — {title}"))


# ── DEV.to API flow ─────────────────────────────────────────────────────────

def _publish_devto(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    api_key: str,
    now_iso: str,
) -> None:
    """Publish a Markdown article to DEV.to as a draft via the Forem REST API."""
    from fgeo.publishers.devto import publish_to_devto  # noqa: PLC0415

    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    markdown_content = src.read_text(encoding="utf-8")
    raw_tags = content.get("tags") or ""
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    result = publish_to_devto(
        title=title,
        markdown_content=markdown_content,
        api_key=api_key,
        tags=tags,
    )

    platform_id = content.get("platform_id") or ""
    draft_url = result.get("url", "")

    if result.get("status") == "failed":
        console.print(f"[red]DEV.to publish failed:[/red] {result.get('message', 'unknown error')}")
        db.create_publish_task(
            task_id=task_id,
            content_id=content_id,
            platform_id=platform_id,
            repo_url="https://dev.to",
            branch="",
            task_dir=str(task_dir),
            pr_url="",
            status="failed",
        )
        raise typer.Exit(1)

    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=platform_id,
        repo_url="https://dev.to",
        branch="",
        task_dir=str(task_dir),
        pr_url=draft_url,
        status="pr_open",
    )
    if draft_url:
        db.update_content(content_id, "published_url", draft_url)

    body = (
        f"[bold]Task ID:[/bold]   {task_id}\n"
        f"[bold]Draft URL:[/bold] {draft_url}\n"
        f"\nOpen the link above on DEV.to to review and publish.\n"
        f"After publishing, run: [bold]fgeo publish task done {task_id}[/bold]"
    )
    console.print(Panel(body, title=f"[green]✓ DEV.to draft created[/green] — {title}"))


def _publish_juejin(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    now_iso: str,
    category_id: str = "",
) -> None:
    """Publish a Markdown article to 掘金 (Juejin) as a draft via the internal API."""
    from fgeo.publishers.juejin import publish_to_juejin, JUEJIN_DEFAULT_CATEGORY  # noqa: PLC0415

    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    raw_markdown = src.read_text(encoding="utf-8")
    _, markdown_content = _parse_frontmatter(raw_markdown)
    effective_category = category_id or JUEJIN_DEFAULT_CATEGORY

    result = publish_to_juejin(
        title=title,
        markdown_content=markdown_content,
        category_id=effective_category,
        task_dir=task_dir,
    )

    platform_id = content.get("platform_id") or ""
    draft_url = result.get("url", "")

    if result.get("status") == "failed":
        console.print(f"[red]掘金 publish failed:[/red] {result.get('message', 'unknown error')}")
        db.create_publish_task(
            task_id=task_id,
            content_id=content_id,
            platform_id=platform_id,
            repo_url="https://juejin.cn",
            branch="",
            task_dir=str(task_dir),
            pr_url="",
            status="failed",
        )
        raise typer.Exit(1)

    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=platform_id,
        repo_url="https://juejin.cn",
        branch="",
        task_dir=str(task_dir),
        pr_url=draft_url,
        status="pr_open",
    )
    if draft_url:
        db.update_content(content_id, "published_url", draft_url)

    body = (
        f"[bold]Task ID:[/bold]   {task_id}\n"
        f"[bold]Draft URL:[/bold] {draft_url}\n"
        f"\nOpen the link above on 掘金 to review and publish.\n"
        f"After publishing, run: [bold]fgeo publish task done {task_id}[/bold]"
    )
    console.print(Panel(body, title=f"[green]✓ 掘金 draft created[/green] — {title}"))


# ── 掘金沸点 pin flow ─────────────────────────────────────────────────────────

def _publish_juejin_pin(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    now_iso: str,
) -> None:
    """Publish a short pin to 掘金沸点 (Juejin Pin) — immediate publish, no draft."""
    from fgeo.publishers.juejin_pin import publish_juejin_pin  # noqa: PLC0415

    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    raw = src.read_text(encoding="utf-8")
    post_text = _strip_md(_strip_frontmatter(raw)).strip()
    post_text = re.sub(r"\n{3,}", "\n\n", post_text).strip()

    char_count = len(post_text)
    if char_count > JUEJIN_PIN_MAX_CHARS:
        console.print(
            f"[red]✗ Content too long for 掘金沸点[/red]\n"
            f"  Current length : [bold]{char_count}[/bold] characters\n"
            f"  Limit          : [bold]{JUEJIN_PIN_MAX_CHARS}[/bold] characters\n\n"
            f"掘金沸点 is a short-form post — please trim your content and try again."
        )
        raise typer.Exit(1)

    result = publish_juejin_pin(post_text, task_dir=task_dir)
    platform_id = content.get("platform_id") or ""

    if result.get("status") == "failed":
        console.print(f"[red]掘金沸点 publish failed:[/red] {result.get('message', 'unknown error')}")
        db.create_publish_task(
            task_id=task_id,
            content_id=content_id,
            platform_id=platform_id,
            repo_url="https://juejin.cn",
            branch="",
            task_dir=str(task_dir),
            pr_url="",
            status="failed",
        )
        raise typer.Exit(1)

    pin_url = result.get("url", "")
    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=platform_id,
        repo_url="https://juejin.cn",
        branch="",
        task_dir=str(task_dir),
        pr_url=pin_url,
        status="merged",
    )
    db.update_content(content_id, "status", "published")
    db.update_content(content_id, "published_at", now_iso)
    if pin_url:
        db.update_content(content_id, "published_url", pin_url)

    console.print(Panel(
        f"[bold]Pin URL:[/bold]  {pin_url}\n"
        f"[bold]Status:[/bold]   [green]published[/green]",
        title=f"[green]✓ 掘金沸点 published[/green] — {title}",
    ))


# ── DEV.to Quickpost flow ────────────────────────────────────────────────────

def _publish_devto_quickpost(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    api_key: str,
    now_iso: str,
) -> None:
    """Publish a short post to DEV.to Quickpost — immediate publish, no draft."""
    from fgeo.publishers.devto_quickpost import publish_devto_quickpost  # noqa: PLC0415

    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    raw = src.read_text(encoding="utf-8")
    post_text = _strip_md(_strip_frontmatter(raw)).strip()
    post_text = re.sub(r"\n{3,}", "\n\n", post_text).strip()

    char_count = len(post_text)
    if char_count > DEVTO_QP_MAX_CHARS:
        console.print(
            f"[red]✗ Content too long for DEV.to Quickpost[/red]\n"
            f"  Current length : [bold]{char_count}[/bold] characters\n"
            f"  Limit          : [bold]{DEVTO_QP_MAX_CHARS}[/bold] characters\n\n"
            f"DEV.to Quickpost is limited to {DEVTO_QP_MAX_CHARS} characters — "
            f"please trim your content and try again."
        )
        raise typer.Exit(1)

    result = publish_devto_quickpost(post_text, api_key=api_key, task_dir=task_dir)
    platform_id = content.get("platform_id") or ""

    if result.get("status") == "failed":
        console.print(f"[red]DEV.to Quickpost failed:[/red] {result.get('message', 'unknown error')}")
        db.create_publish_task(
            task_id=task_id,
            content_id=content_id,
            platform_id=platform_id,
            repo_url="https://dev.to",
            branch="",
            task_dir=str(task_dir),
            pr_url="",
            status="failed",
        )
        raise typer.Exit(1)

    post_url = result.get("url", "")
    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=platform_id,
        repo_url="https://dev.to",
        branch="",
        task_dir=str(task_dir),
        pr_url=post_url,
        status="merged",
    )
    db.update_content(content_id, "status", "published")
    db.update_content(content_id, "published_at", now_iso)
    if post_url:
        db.update_content(content_id, "published_url", post_url)

    console.print(Panel(
        f"[bold]Post URL:[/bold] {post_url}\n"
        f"[bold]Status:[/bold]   [green]published[/green]",
        title=f"[green]✓ DEV.to Quickpost published[/green] — {title}",
    ))


# ── Blog git-PR flow ──────────────────────────────────────────────────────────

def _publish_blog_git(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    publish_url: str,
    now_iso: str,
    force: bool = False,
) -> None:
    """Clone the blog repo, push a branch, open a PR, and create a publish task."""
    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = task_dir / "repo"
    branch = f"fgeo/{content_id}"

    console.print(f"[dim]Cloning {publish_url} …[/dim]")
    clone = _run_git(["clone", publish_url, str(repo_dir)])
    if clone.returncode != 0:
        console.print(f"[red]git clone failed:[/red]\n{clone.stderr}")
        raise typer.Exit(1)

    # Use -B to reset the branch if it already exists (needed when --force)
    _run_git(["checkout", "-B", branch], cwd=repo_dir)

    # Copy article into docs/posts/ (stripping DEV.to frontmatter)
    posts_dir = repo_dir / "docs" / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    dest_name = _with_date_prefix(src.name)
    _, blog_body = _parse_frontmatter(src.read_text(encoding="utf-8"))
    (posts_dir / dest_name).write_text(blog_body, encoding="utf-8")

    _run_git(["add", "-A"], cwd=repo_dir)
    _run_git(["commit", "-m", f"publish: {title}"], cwd=repo_dir)

    console.print("[dim]Pushing branch …[/dim]")
    push_args = ["push", "-u", "origin", branch]
    if force:
        push_args.append("--force-with-lease")
    push = _run_git(push_args, cwd=repo_dir)
    if push.returncode != 0:
        console.print(f"[red]git push failed:[/red]\n{push.stderr}")
        raise typer.Exit(1)

    # Try gh pr create (optional — falls back to compare URL if gh not installed/configured)
    pr_url = ""
    compare_url = f"{_git_remote_to_web_url(publish_url)}/compare/{branch}?expand=1"
    if not shutil.which("gh"):
        console.print(
            "[yellow]GitHub CLI (gh) not found.[/yellow] "
            "Install it to create PRs automatically:\n"
            "  [bold]brew install gh[/bold]  (macOS)\n"
            "  [bold]winget install --id GitHub.cli[/bold]  (Windows)\n"
            "  [bold]https://cli.github.com[/bold]"
        )
    else:
        gh = subprocess.run(
            ["gh", "pr", "create",
             "--title", f"publish: {title}",
             "--body", f"Published via fgeo\n\nContent ID: `{content_id}`",
             "--head", branch],
            cwd=repo_dir, capture_output=True, text=True,
        )
        if gh.returncode == 0 and gh.stdout.strip():
            pr_url = gh.stdout.strip().splitlines()[-1]

    # Record task
    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=content.get("platform_id") or "",
        repo_url=publish_url,
        branch=branch,
        task_dir=str(task_dir),
        pr_url=pr_url,
        status="pr_open",
    )

    body = (
        f"[bold]Branch:[/bold]    {branch}\n"
        f"[bold]Task ID:[/bold]   {task_id}\n"
    )
    if pr_url:
        body += f"[bold]PR URL:[/bold]    {pr_url}\n"
    else:
        body += (
            f"[bold]Open PR:[/bold]   {compare_url}\n"
            f"[dim](gh not available — click the link above to create the PR on GitHub)[/dim]\n"
        )
    body += f"\nAfter merging, run: [bold]fgeo publish task done {task_id}[/bold]"
    console.print(Panel(body, title=f"[green]✓ PR ready[/green] — {title}"))


# ── Blog local-copy flow (fallback when publish_url not set) ─────────────────

def _publish_blog_local(
    db,
    content_id: str,
    title: str,
    src: Path,
    blog_dir: str,
    force: bool,
    workspace: str,
    now_iso: str,
) -> None:
    """Copy article directly into the local blog posts directory."""
    if blog_dir:
        posts_dir = Path(blog_dir)
    elif workspace:
        posts_dir = Path(workspace) / "platforms" / "blog" / "docs" / "posts"
    else:
        console.print("[red]Cannot determine blog posts directory.[/red]")
        console.print("Use [bold]--blog-dir[/bold] to specify the destination folder.")
        raise typer.Exit(1)

    posts_dir.mkdir(parents=True, exist_ok=True)
    dest_name = _with_date_prefix(src.name)
    dest = posts_dir / dest_name

    if dest.exists() and not force:
        console.print(f"[yellow]Destination already exists:[/yellow] {dest}")
        console.print("Use [bold]--force[/bold] to overwrite.")
        raise typer.Exit(1)

    _, blog_body = _parse_frontmatter(src.read_text(encoding="utf-8"))
    dest.write_text(blog_body, encoding="utf-8")
    db.update_content(content_id, "status", "published")
    db.update_content(content_id, "published_at", now_iso)
    db.update_content(content_id, "published_url", str(dest))

    console.print(Panel(
        f"[bold]Source:[/bold]  {src}\n"
        f"[bold]Dest:[/bold]    {dest}\n"
        f"[bold]Status:[/bold]  draft → [green]published[/green]",
        title=f"[green]✓ Published to blog (local)[/green] — {title}",
    ))


# ── WeChat MP (公众号) RPA flow ──────────────────────────────────────────────

def _publish_wechat(
    db,
    content: dict,
    content_id: str,
    title: str,
    src: Path,
    now_iso: str,
) -> None:
    """Convert Markdown to WeChat HTML and publish via Playwright RPA."""
    try:
        from fgeo.converters.wechat_html import md_to_wechat_html  # noqa: PLC0415
    except ImportError:
        console.print("[red]WeChat HTML converter not found.[/red]")
        raise typer.Exit(1)

    try:
        from fgeo.publishers.wechat import publish_to_wechat  # noqa: PLC0415
    except ImportError:
        console.print(
            "[red]Playwright not installed.[/red]\n"
            "Run: [bold]pip install fgeo\\[publish][/bold]\n"
            "Then: [bold]playwright install chromium[/bold]"
        )
        raise typer.Exit(1)

    task_id = _make_task_id(content_id)
    task_dir = FGEO_HOME / "publish" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Convert Markdown → WeChat HTML
    console.print("[dim]Converting Markdown to WeChat HTML…[/dim]")
    html_content, fm = md_to_wechat_html(src)

    # Save converted HTML for reference
    html_file = task_dir / "article.html"
    html_file.write_text(html_content, encoding="utf-8")
    console.print(f"[dim]HTML saved to {html_file}[/dim]")

    # Step 2: Extract metadata
    author = fm.get("author", "")
    digest = fm.get("digest", fm.get("description", ""))

    # Step 3: Publish via Playwright RPA
    console.print("[bold]Launching browser for WeChat MP…[/bold]")
    result = publish_to_wechat(
        title=title,
        html_content=html_content,
        author=author,
        digest=digest,
        headless=False,
        save_only=True,
        task_dir=task_dir,
    )

    # Step 4: Record publish task
    platform_id = content.get("platform_id") or ""
    status = "pr_open" if result["status"] == "draft_saved" else "failed"

    db.create_publish_task(
        task_id=task_id,
        content_id=content_id,
        platform_id=platform_id,
        repo_url="https://mp.weixin.qq.com",
        branch="",
        task_dir=str(task_dir),
        pr_url=result.get("url", ""),
        status=status,
    )

    if status == "pr_open":
        body = (
            f"[bold]Task ID:[/bold]   {task_id}\n"
            f"[bold]HTML:[/bold]      {html_file}\n"
            f"[bold]Status:[/bold]    draft saved in WeChat MP\n"
            f"\nArticle is now in your WeChat MP draft box.\n"
            f"After publishing in WeChat MP, run:\n"
            f"  [bold]fgeo publish task done {task_id}[/bold]"
        )
        console.print(Panel(body, title=f"[green]✓ WeChat MP draft saved[/green] — {title}"))
    else:
        db.update_publish_task(task_id, "status", "failed")
        console.print(
            f"[red]✗ WeChat publish failed:[/red] {result.get('message', 'unknown error')}\n"
            f"[dim]HTML file saved at: {html_file}[/dim]\n"
            f"[dim]You can manually copy the HTML content to mp.weixin.qq.com[/dim]"
        )
        raise typer.Exit(1)


# ── publish content ───────────────────────────────────────────────────────────

@publish_app.command("content")
def publish_content(
    content_id: str = typer.Argument(help="Content ID to publish"),
    blog_dir: str = typer.Option("", "--blog-dir", help="(local mode) Override blog posts directory"),
    url: str = typer.Option("", "--url", help="Published URL to record (non-blog platforms)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite destination file (local mode) / force-push branch (git mode)"),
) -> None:
    """Publish a content item to its platform.

    Supported platforms and their publish flow:

    \b
      blog           Git clone → branch → commit → push → PR → task (pr_open).
                     Falls back to local file copy when publish_url is not set.
      medium         Playwright RPA → paste into editor → draft URL (pr_open).
      公众号          Playwright RPA → QR login → paste HTML → draft (pr_open).
      bluesky        AT Protocol API → direct post (published immediately).
      devto          Forem REST API → draft on dev.to (pr_open).
      掘金 / juejin  Playwright cookie login → Juejin API → draft (pr_open).
      掘金沸点 / juejin-pin
                     Juejin Pin API (reuses 掘金 cookies) → published immediately.
      devto-quickpost
                     Forem REST API with published:true → published immediately.
      other          Mark as published and record URL (--url).
    """
    db = get_db()
    content = db.get_content(content_id)
    if not content:
        console.print(f"[red]Content not found:[/red] {content_id}")
        raise typer.Exit(1)

    if content["status"] == "published":
        console.print(f"[yellow]Already published:[/yellow] {content_id}")
        raise typer.Exit(0)

    platform = _resolve_platform_row(db, content.get("platform_id"))
    platform_name = platform.get("name") or ""
    publish_url = platform.get("publish_url") or ""
    source_path = content.get("source_path") or ""
    workspace = content.get("workspace") or ""
    now_iso = datetime.now().isoformat(timespec="seconds")
    title = content.get("title") or content_id

    # Non-blocking frontmatter check — warns if DEV.to metadata fields are missing.
    # The frontmatter is the canonical metadata record for all articles; non-devto
    # platforms strip it before uploading.
    if source_path and Path(source_path).suffix.lower() == ".md":
        _check_devto_frontmatter(Path(source_path))

    if platform_name == BLOG_PLATFORM:
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        if publish_url:
            _publish_blog_git(db, content, content_id, title, src, publish_url, now_iso, force=force)
        else:
            _publish_blog_local(db, content_id, title, src, blog_dir, force, workspace, now_iso)

    elif platform_name == BSKY_PLATFORM:
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        bsky_handle = platform.get("bsky_handle") or ""
        app_password = platform.get("platform_secret") or ""
        if not bsky_handle:
            console.print(
                "[red]Bluesky handle not set.[/red]\n"
                f"Run: [bold]fgeo platform set <proj> bluesky bsky_handle marvintalk.bsky.social[/bold]"
            )
            raise typer.Exit(1)
        if not app_password:
            console.print(
                "[red]Bluesky app password not set.[/red]\n"
                "Run: [bold]fgeo platform set <proj> bluesky platform_secret <app-password>[/bold]\n"
                "[dim]Get an app password at: https://bsky.app/settings/app-passwords[/dim]"
            )
            raise typer.Exit(1)

        _publish_bsky(db, content, content_id, title, src, bsky_handle, app_password, now_iso)

    elif platform_name == MEDIUM_PLATFORM:
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        if "```mermaid" in src.read_text(encoding="utf-8"):
            console.print(f"[red]Error: Mermaid diagrams found in Markdown (content: {content_id}).[/red]")
            console.print("Please replace Mermaid code blocks with rendered images before publishing.")
            console.print(
                "建议使用开源制图服务 Kroki.io：用 Python base64/zlib 压缩函数"
                "将 Mermaid 源码编码成可渲染图片的 URL，"
                "再把 Markdown 文件里的 ```mermaid 代码块替换成图片引用即可。"
            )
            raise typer.Exit(1)

        _publish_medium(db, content, content_id, title, src, now_iso)

    elif platform_name == WECHAT_PLATFORM:
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        _publish_wechat(db, content, content_id, title, src, now_iso)

    elif platform_name == DEVTO_PLATFORM:
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        api_key = platform.get("platform_secret") or ""
        if not api_key:
            console.print(
                "[red]DEV.to API key not set.[/red]\n"
                "Run: [bold]fgeo platform set <proj> devto platform_secret <api-key>[/bold]\n"
                "[dim]Get your API key at: https://dev.to/settings/extensions[/dim]"
            )
            raise typer.Exit(1)

        _publish_devto(db, content, content_id, title, src, api_key, now_iso)

    elif platform_name in (JUEJIN_PLATFORM, JUEJIN_PLATFORM_ALT):
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        category_id = publish_url  # publish_url stores category_id for Juejin
        _publish_juejin(db, content, content_id, title, src, now_iso, category_id)

    elif platform_name in (JUEJIN_PIN_PLATFORM, JUEJIN_PIN_PLATFORM_ALT):
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        _publish_juejin_pin(db, content, content_id, title, src, now_iso)

    elif platform_name == DEVTO_QP_PLATFORM:
        if not source_path:
            console.print("[red]No source file path recorded for this content.[/red]")
            console.print(f"Run: [bold]fgeo content set {content_id} source_path <path>[/bold]")
            raise typer.Exit(1)

        src = Path(source_path)
        if not src.exists():
            console.print(f"[red]Source file not found:[/red] {source_path}")
            raise typer.Exit(1)

        api_key = platform.get("platform_secret") or ""
        if not api_key:
            console.print(
                "[red]DEV.to API key not set.[/red]\n"
                "Run: [bold]fgeo platform set <proj> devto-quickpost platform_secret <api-key>[/bold]\n"
                "[dim]Get your API key at: https://dev.to/settings/extensions[/dim]"
            )
            raise typer.Exit(1)

        _publish_devto_quickpost(db, content, content_id, title, src, api_key, now_iso)

    else:
        db.update_content(content_id, "status", "published")
        db.update_content(content_id, "published_at", now_iso)
        if url:
            db.update_content(content_id, "published_url", url)

        body = f"[bold]Platform:[/bold] {platform_name or 'unknown'}\n"
        body += f"[bold]Status:[/bold]  draft → [green]published[/green]\n"
        if url:
            body += f"[bold]URL:[/bold]     {url}"
        else:
            body += "[dim]Tip: use --url to record the published URL.[/dim]"

        console.print(Panel(body, title=f"[green]✓ Marked as published[/green] — {title}"))


# ── publish list ──────────────────────────────────────────────────────────────

@publish_app.command("list")
def list_publishable(
    project: str = typer.Option("", "--project", "-p", help="Filter by project name"),
    platform: str = typer.Option("", "--platform", help="Filter by platform name"),
    status: str = typer.Option("draft", "--status", "-s", help="Status filter (default: draft)"),
) -> None:
    """List content items ready to publish."""
    db = get_db()
    items = db.list_contents(
        project_name=project,
        platform_name=platform if project else "",
        status=status,
    )

    if not items:
        console.print(f"[yellow]No content with status '{status}'.[/yellow]")
        return

    table = Table(title=f"📋 Publishable Content — status={status}")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Platform")
    table.add_column("Project")
    table.add_column("Source File")

    for item in items:
        src = item.get("source_path") or ""
        table.add_row(
            item["id"],
            (item.get("title") or "")[:42],
            item.get("platform_name") or "—",
            item.get("project_name") or "—",
            Path(src).name if src else "—",
        )
    console.print(table)


# ── publish task subcommands ──────────────────────────────────────────────────

@task_app.command("list")
def task_list(
    status: str = typer.Option("", "--status", "-s", help="Filter: pr_open, merged, failed"),
    content_id: str = typer.Option("", "--content", "-c", help="Filter by content ID"),
) -> None:
    """List publish tasks."""
    db = get_db()
    tasks = db.list_publish_tasks(status=status, content_id=content_id)

    if not tasks:
        msg = f"No publish tasks{' with status ' + status if status else ''}."
        console.print(f"[yellow]{msg}[/yellow]")
        return

    STATUS_COLOR = {"pr_open": "yellow", "merged": "green", "failed": "red"}
    table = Table(title="📬 Publish Tasks")
    table.add_column("Task ID", style="dim")
    table.add_column("Content")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("PR URL")
    table.add_column("Created")

    for t in tasks:
        color = STATUS_COLOR.get(t["status"], "white")
        table.add_row(
            t["id"],
            (t.get("content_title") or t.get("content_id") or "")[:36],
            (t.get("branch") or "")[:40],
            f"[{color}]{t['status']}[/{color}]",
            t.get("pr_url") or "—",
            (t.get("created_at") or "")[:16],
        )
    console.print(table)


@task_app.command("show")
def task_show(
    task_id: str = typer.Argument(help="Publish task ID"),
) -> None:
    """Show details of a publish task."""
    db = get_db()
    task = db.get_publish_task(task_id)
    if not task:
        console.print(f"[red]Task not found:[/red] {task_id}")
        raise typer.Exit(1)

    info = (
        f"[bold]ID:[/bold]         {task['id']}\n"
        f"[bold]Content:[/bold]    {task['content_id']}\n"
        f"[bold]Status:[/bold]     {task['status']}\n"
        f"[bold]Branch:[/bold]     {task.get('branch') or '—'}\n"
        f"[bold]Repo URL:[/bold]   {task.get('repo_url') or '—'}\n"
        f"[bold]PR URL:[/bold]     {task.get('pr_url') or '—'}\n"
        f"[bold]Task Dir:[/bold]   {task.get('task_dir') or '—'}\n"
        f"[bold]Created:[/bold]    {task.get('created_at') or '—'}\n"
    )
    if task["status"] == "pr_open":
        info += f"\n[dim]After merging, run:[/dim] [bold]fgeo publish task done {task_id}[/bold]"
    console.print(Panel(info, title=f"Publish Task — {task_id}"))


@task_app.command("done")
def task_done(
    task_id: str = typer.Argument(help="Task ID to mark as merged/published"),
) -> None:
    """Mark a publish task as merged and update content status to published."""
    db = get_db()
    task = db.get_publish_task(task_id)
    if not task:
        console.print(f"[red]Task not found:[/red] {task_id}")
        raise typer.Exit(1)

    if task["status"] == "merged":
        console.print(f"[yellow]Task already merged:[/yellow] {task_id}")
        raise typer.Exit(0)

    db.update_publish_task(task_id, "status", "merged")

    content_id = task["content_id"]
    now_iso = datetime.now().isoformat(timespec="seconds")
    db.update_content(content_id, "status", "published")
    db.update_content(content_id, "published_at", now_iso)
    if task.get("pr_url"):
        db.update_content(content_id, "published_url", task["pr_url"])

    console.print(Panel(
        f"[bold]Task:[/bold]     {task_id}\n"
        f"[bold]Content:[/bold]  {content_id}\n"
        f"[bold]Status:[/bold]   pr_open → [green]merged[/green]\n"
        f"[bold]Content:[/bold]  → [green]published[/green]",
        title="[green]✓ Task done — content published[/green]",
    ))
