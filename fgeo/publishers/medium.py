"""Medium publisher via Playwright RPA.

Automates medium.com to:
1. Open a dedicated fgeo-managed Chrome profile via
   ``launch_persistent_context`` — completely separate from the user's
   running Chrome, no conflicts.
2. Navigate to medium.com/new-story, fill title and paste HTML body.
3. Wait for Medium auto-save and return the draft URL.

First run: a new Chrome window opens and the user logs in to Medium once.
Subsequent runs: the session is persisted in ``~/.fgeo/medium/chrome-profile/``
so no re-login is needed.

DOM selectors confirmed from live Medium editor (2026-03), cross-referenced with
doocs/cose medium.js (https://github.com/doocs/cose):
  h3.graf--title       -- article title (contenteditable)
  p.graf--p            -- first body paragraph (paste target)

Requires: ``pip install fgeo[publish]`` (playwright + playwright install chrome)

Usage::

    from fgeo.publishers.medium import publish_to_medium

    result = publish_to_medium(
        title="My Article",
        markdown_content="# Hello\n\nBody text ...",
    )
    # result = {"status": "draft_saved", "url": "https://medium.com/@user/...", "message": "..."}

Note: Medium Integration Token API was deprecated in 2024/2025 and is no longer
available to new users. This Playwright RPA approach works for all Medium accounts.
"""

from __future__ import annotations

import json
import os
import platform
import re
import time
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

MEDIUM_DATA_DIR = Path.home() / ".fgeo" / "medium"
FGEO_CHROME_PROFILE = MEDIUM_DATA_DIR / "chrome-profile"

MEDIUM_HOME = "https://medium.com"
MEDIUM_NEW_STORY = "https://medium.com/new-story"

# Selectors (confirmed from live DOM + doocs/cose)
SEL_TITLE = "h3.graf--title"
SEL_BODY = "p.graf--p"
# Publish button in top nav bar (data-action="show-prepublish")
SEL_PUBLISH_BTN = "button.js-publishButton"
# Confirm button inside the pre-publish dialog
SEL_PUBLISH_NOW = "button[data-action='publish']"


# -- Playwright availability --------------------------------------------------

def _check_playwright() -> None:
    """Ensure playwright is installed (raise SystemExit with friendly message if not)."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        console.print(
            "[red]playwright not installed.[/red]\n"
            "Run: [bold]pip install fgeo[publish][/bold]\n"
            "Then: [bold]playwright install chrome[/bold]"
        )
        raise SystemExit(1)


# -- Markdown -> HTML (minimal, Medium-compatible) ----------------------------

def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter (--- ... ---) from Markdown text."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        return parts[2].lstrip("\n") if len(parts) >= 3 else text
    return text


def _inline_md(text: str) -> str:
    """Apply inline Markdown formatting: bold, italic, code, links, images."""
    # Medium always tries to re-upload any <img src="..."> to its own CDN when
    # content is pasted, which causes "Something went wrong uploading the image"
    # errors for SVGs, external CDN images, etc.  The only reliable approach is
    # to strip all images entirely and keep just the alt text as a styled caption.
    def _img(m: re.Match) -> str:
        alt = m.group(1)
        return f"<em>[图: {alt}]</em>" if alt else ""
    text = re.sub(r"!\[([^\]]*)\]\(([^\)]+)\)", _img, text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    # Strikethrough
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    return text


def _md_to_html(md: str) -> str:
    """Convert Markdown to minimal HTML suitable for pasting into Medium editor."""
    text = md.strip()

    def _replace_code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = m.group(2).rstrip("\n")
        if lang == "mermaid":
            # Wrap for mermaid.js rendering (handled in _fill_medium_article)
            return f'<div class="mermaid">{code.strip()}</div>'
        # HTML-escape content so < > & don't break the markup,
        # then replace \n with <br> so Medium's paste handler treats the
        # entire block as ONE element — preventing # lines from becoming
        # headings and blank lines from creating garbage <pre> blocks.
        # Blank lines (\n\n) become <br>&nbsp;<br> so Medium never sees
        # a true empty line that would trigger a paragraph/block split.
        escaped = (
            code.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n\n", "\n&nbsp;\n")  # guard blank lines first
                .replace("\n", "<br>")
        )
        lang_attr = f' class="language-{lang}"' if lang else ""
        return f'<pre style="font-family:monospace;background:#f6f8fa;padding:1em;overflow-x:auto"><code{lang_attr}>{escaped}</code></pre>'

    text = re.sub(r"```(\w*)\n(.*?)```", _replace_code_block, text, flags=re.DOTALL)

    lines = text.split("\n")
    html_parts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Headings
        h_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if h_match:
            level = len(h_match.group(1))
            html_parts.append(f"<h{level}>{_inline_md(h_match.group(2))}</h{level}>")
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            html_parts.append(f"<blockquote><p>{_inline_md(line[2:])}</p></blockquote>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            html_parts.append("<hr>")
            i += 1
            continue

        # Pre-rendered code block (from substitution above)
        if line.startswith("<pre"):  # catches both <pre> and <pre style=...>
            html_parts.append(line)
            i += 1
            continue

        # Skip blank lines
        if not line.strip():
            i += 1
            continue

        # Unordered list
        if re.match(r"^[-*+]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i]):
                item_text = re.sub(r"^[-*+]\s+", "", lines[i])
                items.append(f"<li>{_inline_md(item_text)}</li>")
                i += 1
            html_parts.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                item_text = re.sub(r"^\d+\.\s+", "", lines[i])
                items.append(f"<li>{_inline_md(item_text)}</li>")
                i += 1
            html_parts.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Paragraph
        para_lines = []
        while i < len(lines) and lines[i].strip():
            if re.match(r"^(#{1,6}|[-*+]\s|> |```|\d+\.)", lines[i]):
                break
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            html_parts.append(f"<p>{_inline_md(' '.join(para_lines))}</p>")
        # Skip a blank line separator; if we stopped at a pattern (heading/list) let outer loop re-process it
        if i < len(lines) and not lines[i].strip():
            i += 1

    return "\n".join(html_parts)


_SET_TITLE_JS = """
(el, title) => {
    el.focus();
    el.textContent = title;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
}
""".strip()


# -- Login check -------------------------------------------------------------

def _is_logged_in(page: Any) -> bool:
    """Navigate to /me/settings; not logged in if Medium redirects to /m/signin."""
    try:
        page.goto(MEDIUM_HOME + "/me/settings", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        url = page.url
        path = url.split("?")[0].rstrip("/")
        return "medium.com" in url and not path.endswith(("/m/signin", "/m/login"))
    except Exception:
        return False


def _wait_for_login(page: Any, timeout_sec: int = 180) -> bool:  # noqa: ARG001
    """Open the Medium sign-in page and prompt the user to log in manually.

    After the browser opens, print a simple CLI menu and wait for the user
    to type their choice:

      1 — already logged in → proceed
      2 — quit → abort publish
    """
    console.print("[bold yellow]Not logged in to Medium.[/bold yellow]")
    console.print("Opening the Medium sign-in page in the browser…")
    page.goto(MEDIUM_HOME + "/m/signin", wait_until="domcontentloaded", timeout=20000)

    console.print("")
    console.print("Please sign in to Medium in the browser window, then come back here.")
    console.print("")

    while True:
        console.print("  [bold]1.[/bold] 已登录，继续发布")
        console.print("  [bold]2.[/bold] 放弃，退出")
        choice = input("请选择 (1/2): ").strip()
        if choice == "1":
            console.print("[green]OK，继续…[/green]")
            return True
        if choice == "2":
            console.print("[yellow]已取消。[/yellow]")
            return False
        console.print("[red]请输入 1 或 2。[/red]")


# -- Editor interaction -------------------------------------------------------

def _fill_medium_article(page: Any, title: str, html_content: str) -> bool:
    """Fill the Medium new-story editor with title and body.

    Strategy — mimics what VS Code Markdown Preview copy does:
      1. Render the article HTML via ``page.set_content()`` in the current tab.
      2. ``Cmd/Ctrl+A`` → ``Cmd/Ctrl+C`` — browser native copy writes real
         ``text/html`` to the OS clipboard (no synthetic ClipboardEvent tricks).
      3. Navigate to medium.com/new-story.
      4. Set title via JS, click body, ``Cmd/Ctrl+V`` — Medium reads the real
         clipboard and preserves headings, bold, code blocks, etc.
    """
    mod = "Meta" if platform.system() == "Darwin" else "Control"

    # Step 1: Render HTML (with Mermaid.js) in this tab and copy to OS clipboard
    console.print("[dim]Rendering HTML for clipboard copy...[/dim]")
    try:
        # Wrap content in a full page so mermaid.js can render diagrams before copy
        has_mermaid = 'class="mermaid"' in html_content
        mermaid_script = (
            '<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>'
            '<script>mermaid.initialize({startOnLoad:true});</script>'
            if has_mermaid else ""
        )
        full_page = (
            f"<!DOCTYPE html><html><head>"
            f"<meta charset='utf-8'>"
            f"<style>body{{font-family:sans-serif;line-height:1.6;max-width:860px;margin:40px auto;padding:0 20px}}"
            f"img{{max-width:100%}} pre{{background:#f6f8fa;padding:1em;overflow-x:auto}}</style>"
            f"{mermaid_script}"
            f"</head><body>{html_content}</body></html>"
        )
        page.set_content(full_page, wait_until="domcontentloaded")
        if has_mermaid:
            # Give mermaid.js time to render SVGs
            console.print("[dim]Waiting for Mermaid diagrams to render...[/dim]")
            time.sleep(3)
        else:
            time.sleep(0.5)
        page.keyboard.press(f"{mod}+a")  # select all rendered content
        time.sleep(0.3)
        page.keyboard.press(f"{mod}+c")  # copy with real text/html to OS clipboard
        time.sleep(0.5)
        console.print("[green]HTML copied to clipboard[/green]")
    except Exception as exc:
        console.print(f"[red]Failed to copy HTML:[/red] {exc}")
        return False

    # Step 2: Navigate to Medium editor
    console.print("[dim]Navigating to Medium new-story editor...[/dim]")
    page.goto(MEDIUM_NEW_STORY, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # Step 3: Fill title
    console.print("[dim]Filling article title...[/dim]")
    try:
        title_el = page.locator(SEL_TITLE)
        title_el.wait_for(state="visible", timeout=15000)
        title_el.click()
        time.sleep(0.3)
        title_el.evaluate(_SET_TITLE_JS, title)
        time.sleep(0.5)
        console.print("[green]Title set[/green]")
    except Exception as exc:
        console.print(f"[red]Failed to set title:[/red] {exc}")
        return False

    # Step 4: Paste body from real OS clipboard
    console.print("[dim]Pasting article body from clipboard...[/dim]")
    try:
        body_el = page.locator(SEL_BODY).first
        body_el.wait_for(state="visible", timeout=10000)
        body_el.click()
        time.sleep(0.5)
        page.keyboard.press(f"{mod}+v")
        time.sleep(1)
        console.print("[green]Body pasted[/green]")
    except Exception as exc:
        console.print(f"[red]Failed to paste body:[/red] {exc}")
        return False

    return True


def _wait_for_autosave(page: Any, max_wait: int = 15) -> str:
    """Wait for Medium auto-save and return the unique draft URL."""
    console.print("[dim]Waiting for Medium auto-save...[/dim]")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(2)
        url = page.url
        if url and "new-story" not in url and "medium.com" in url:
            console.print(f"[green]Draft auto-saved: {url}[/green]")
            return url
    console.print(f"[yellow]Auto-save not detected; current URL: {page.url}[/yellow]")
    return page.url


def _click_publish(
    page: Any,
    subtitle: str = "",
    tags: list[str] | None = None,
) -> bool:
    """Open the pre-publish panel, fill metadata, then click Publish.

    Flow (confirmed from live Medium DOM 2026-03):
      1. Click ``button.js-publishButton`` in the top nav bar.
      2. A right-side panel slides in with preview title, subtitle, topics.
      3. Optionally fill subtitle / tags.
      4. Click the green ``Publish`` button at the bottom of the panel.
    """
    tags = tags or []

    # Step 1: open the pre-publish panel
    console.print("[dim]Clicking Publish button…[/dim]")
    try:
        btn = page.locator(SEL_PUBLISH_BTN)
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
    except Exception as exc:
        console.print(f"[red]Publish button not found:[/red] {exc}")
        return False

    time.sleep(2)  # wait for panel animation

    # Step 2: fill subtitle
    if subtitle:
        console.print("[dim]Filling preview subtitle…[/dim]")
        try:
            sub_el = page.locator('textarea[aria-label="Story preview subtitle"]')
            sub_el.wait_for(state="visible", timeout=8000)
            sub_el.triple_click()  # select existing placeholder text
            sub_el.fill(subtitle)
            time.sleep(0.3)
            console.print("[green]Subtitle set[/green]")
        except Exception as exc:
            console.print(f"[yellow]Could not set subtitle:[/yellow] {exc}")

    # Step 3: add topics / tags
    if tags:
        console.print(f"[dim]Adding {len(tags)} topic(s)…[/dim]")
        try:
            tag_input = page.locator('input[placeholder="Add a topic..."]')
            tag_input.wait_for(state="visible", timeout=8000)
            for tag in tags[:5]:  # Medium allows max 5 topics
                tag_input.click()
                tag_input.type(tag, delay=50)
                time.sleep(0.5)
                page.keyboard.press("Enter")
                time.sleep(0.4)
            console.print("[green]Topics added[/green]")
        except Exception as exc:
            console.print(f"[yellow]Could not add topics:[/yellow] {exc}")

    # Step 4: click the final Publish button
    console.print("[dim]Clicking final Publish button…[/dim]")
    try:
        # Selector: button whose visible text is exactly "Publish"
        publish_btn = page.get_by_role("button", name="Publish", exact=True)
        publish_btn.wait_for(state="visible", timeout=10000)
        publish_btn.click()
    except Exception as exc:
        console.print(f"[red]Publish confirm button not found:[/red] {exc}")
        return False

    time.sleep(3)
    console.print("[green]Article published![/green]")
    return True


# -- Public entry point -------------------------------------------------------

def publish_to_medium(
    title: str,
    markdown_content: str,
    *,
    subtitle: str = "",
    tags: list[str] | None = None,
    headless: bool = False,
    task_dir: Path | None = None,
) -> dict[str, str]:
    """Publish a Markdown article to Medium via Playwright RPA.

    Uses a dedicated fgeo-managed Chrome profile at
    ``~/.fgeo/medium/chrome-profile/``, completely separate from the user's
    normal Chrome — no conflicts, no profile corruption.

    First run: a Chrome window opens and the user logs in to Medium once.
    Subsequent runs: the session persists, no re-login needed.

    Args:
        title: Article title.
        markdown_content: Full Markdown text (frontmatter stripped automatically).
        subtitle: Optional preview subtitle shown on Medium story cards.
        tags: Up to 5 topic tags (e.g. ["AI", "Programming", "Python"]).
        headless: Run headless (False by default; first login must be headed).
        task_dir: If set, saves article.md and article.html here.

    Returns:
        ``{"status": "published" | "draft_saved" | "failed", "url": "...", "message": "..."}``
    """
    _check_playwright()
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    result: dict[str, str] = {"status": "failed", "url": "", "message": ""}

    body_md = _strip_frontmatter(markdown_content)
    html_content = _md_to_html(body_md)

    if task_dir:
        task_dir = Path(task_dir)
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "article.md").write_text(markdown_content, encoding="utf-8")
        (task_dir / "article.html").write_text(html_content, encoding="utf-8")

    FGEO_CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
    console.print(
        "[dim]Opening fgeo Chrome profile at "
        f"[bold]{FGEO_CHROME_PROFILE}[/bold]…[/dim]"
    )

    with sync_playwright() as p:
        context = None
        try:
            context = p.chromium.launch_persistent_context(
                str(FGEO_CHROME_PROFILE),
                channel="chrome",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1400, "height": 900},
            )

            page = context.new_page()

            if not _is_logged_in(page):
                console.print("[yellow]Not logged in to Medium — please sign in.[/yellow]")
                if not _wait_for_login(page, timeout_sec=180):
                    result["message"] = "Login timed out"
                    return result

            if not _fill_medium_article(page, title, html_content):
                result["message"] = "Failed to fill article content"
                return result

            draft_url = _wait_for_autosave(page)

            if not _click_publish(page, subtitle=subtitle, tags=tags or []):
                # Fall back to draft — user can publish manually
                result["status"] = "draft_saved"
                result["url"] = draft_url
                result["message"] = "Article saved as draft (auto-publish failed — open draft URL to publish manually)"
            else:
                published_url = page.url
                result["status"] = "published"
                result["url"] = published_url or draft_url
                result["message"] = "Article published to Medium"

        except KeyboardInterrupt:
            result["message"] = "Cancelled by user"
            console.print("\n[yellow]Medium publish cancelled.[/yellow]")

        except Exception as exc:
            result["message"] = f"Unexpected error: {exc}"
            console.print(f"[red]Error during Medium publish:[/red] {exc}")

        finally:
            try:
                if context:
                    context.close()
            except Exception:
                pass  # suppress TargetClosedError on Ctrl+C

    return result
