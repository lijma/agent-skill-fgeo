"""Markdown → WeChat Official Account HTML converter.

Converts standard Markdown to HTML with inline styles compatible with
WeChat MP (微信公众号) rich-text editor. WeChat strips <style> tags and
CSS classes, so every element must carry its own inline ``style`` attribute.

Design inspired by doocs/md (https://github.com/doocs/md) default theme,
adapted for pure-Python server-side rendering without a browser.

Usage::

    from fgeo.converters.wechat_html import md_to_wechat_html

    html = md_to_wechat_html(Path("article.md"))
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ── Default WeChat inline styles (inspired by doocs/md default theme) ─────────
# Primary color: classic blue #0F4C81
# Font stack: Apple system fonts → PingFang → Microsoft YaHei → Arial → sans-serif

PRIMARY_COLOR = "#0F4C81"
FONT_FAMILY = (
    "-apple-system-font, BlinkMacSystemFont, 'Helvetica Neue', "
    "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei UI', "
    "'Microsoft YaHei', Arial, sans-serif"
)
TEXT_COLOR = "#333333"
CODE_COLOR = "#d14"
CODE_BG = "rgba(27, 31, 35, 0.05)"
LINK_COLOR = "#576b95"
BLOCKQUOTE_BG = "#f7f7f7"
TABLE_BORDER = "#dfdfdf"

# Element-level style mappings
STYLES: dict[str, str] = {
    "container": (
        f"font-family: {FONT_FAMILY}; "
        f"font-size: 16px; "
        f"color: {TEXT_COLOR}; "
        f"line-height: 1.75; "
        f"word-break: break-word; "
        f"overflow-wrap: break-word;"
    ),
    "h1": (
        f"display: table; "
        f"padding: 0 1em; "
        f"border-bottom: 2px solid {PRIMARY_COLOR}; "
        f"margin: 2em auto 1em; "
        f"color: {TEXT_COLOR}; "
        f"font-size: 1.2em; "
        f"font-weight: bold; "
        f"text-align: center;"
    ),
    "h2": (
        f"display: table; "
        f"padding: 0 0.2em; "
        f"margin: 4em auto 2em; "
        f"color: #fff; "
        f"background: {PRIMARY_COLOR}; "
        f"font-size: 1.2em; "
        f"font-weight: bold; "
        f"text-align: center;"
    ),
    "h3": (
        f"padding-left: 8px; "
        f"border-left: 3px solid {PRIMARY_COLOR}; "
        f"margin: 2em 8px 0.75em 0; "
        f"color: {TEXT_COLOR}; "
        f"font-size: 1.1em; "
        f"font-weight: bold; "
        f"line-height: 1.2;"
    ),
    "h4": (
        f"margin: 2em 8px 0.5em; "
        f"color: {PRIMARY_COLOR}; "
        f"font-size: 1em; "
        f"font-weight: bold;"
    ),
    "h5": (
        f"margin: 1.5em 8px 0.5em; "
        f"color: {PRIMARY_COLOR}; "
        f"font-size: 1em; "
        f"font-weight: bold;"
    ),
    "h6": (
        f"margin: 1.5em 8px 0.5em; "
        f"font-size: 1em; "
        f"color: {PRIMARY_COLOR};"
    ),
    "p": (
        f"margin: 1.5em 8px; "
        f"letter-spacing: 0.1em; "
        f"color: {TEXT_COLOR};"
    ),
    "blockquote": (
        f"font-style: normal; "
        f"padding: 1em; "
        f"border-left: 4px solid {PRIMARY_COLOR}; "
        f"border-radius: 6px; "
        f"color: {TEXT_COLOR}; "
        f"background: {BLOCKQUOTE_BG}; "
        f"margin-bottom: 1em;"
    ),
    "blockquote_p": (
        f"display: block; "
        f"font-size: 1em; "
        f"letter-spacing: 0.1em; "
        f"color: {TEXT_COLOR}; "
        f"margin: 0;"
    ),
    "code_inline": (
        f"font-size: 90%; "
        f"color: {CODE_COLOR}; "
        f"background: {CODE_BG}; "
        f"padding: 3px 5px; "
        f"border-radius: 4px;"
    ),
    "code_block": (
        f"font-size: 90%; "
        f"overflow-x: auto; "
        f"border-radius: 8px; "
        f"padding: 1em; "
        f"line-height: 1.5; "
        f"margin: 10px 8px; "
        f"background: #1e1e1e; "
        f"color: #d4d4d4;"
    ),
    "code_block_code": (
        f"display: block; "
        f"overflow-x: auto; "
        f"color: #d4d4d4; "
        f"background: none; "
        f"white-space: pre; "
        f"margin: 0; "
        f"padding: 0;"
    ),
    "strong": (
        f"color: {PRIMARY_COLOR}; "
        f"font-weight: bold;"
    ),
    "em": (
        f"font-style: italic;"
    ),
    "a": (
        f"color: {LINK_COLOR}; "
        f"text-decoration: none;"
    ),
    "img": (
        f"display: block; "
        f"max-width: 100%; "
        f"margin: 0.1em auto 0.5em; "
        f"border-radius: 4px;"
    ),
    "ul": (
        f"list-style: circle; "
        f"padding-left: 1em; "
        f"margin-left: 0; "
        f"color: {TEXT_COLOR};"
    ),
    "ol": (
        f"padding-left: 1em; "
        f"margin-left: 0; "
        f"color: {TEXT_COLOR};"
    ),
    "li": (
        f"display: block; "
        f"margin: 0.2em 8px; "
        f"color: {TEXT_COLOR};"
    ),
    "hr": (
        f"border-style: solid; "
        f"border-width: 2px 0 0; "
        f"border-color: rgba(0, 0, 0, 0.1); "
        f"height: 0; "
        f"margin: 1.5em 0;"
    ),
    "table": (
        f"border-collapse: collapse; "
        f"color: {TEXT_COLOR}; "
        f"width: 100%;"
    ),
    "table_section": (
        f"max-width: 100%; "
        f"overflow: auto;"
    ),
    "th": (
        f"border: 1px solid {TABLE_BORDER}; "
        f"padding: 0.25em 0.5em; "
        f"color: {TEXT_COLOR}; "
        f"word-break: keep-all; "
        f"background: rgba(0, 0, 0, 0.05); "
        f"font-weight: bold;"
    ),
    "td": (
        f"border: 1px solid {TABLE_BORDER}; "
        f"padding: 0.25em 0.5em; "
        f"color: {TEXT_COLOR}; "
        f"word-break: keep-all;"
    ),
    "figure": (
        f"margin: 1.5em 8px; "
        f"color: {TEXT_COLOR};"
    ),
    "figcaption": (
        f"text-align: center; "
        f"color: #888; "
        f"font-size: 0.8em;"
    ),
    "footnote": (
        f"margin: 0.5em 8px; "
        f"font-size: 80%; "
        f"color: {TEXT_COLOR};"
    ),
}


def _s(element: str) -> str:
    """Get inline style string for an element."""
    return STYLES.get(element, "")


# ── Markdown parsing helpers ──────────────────────────────────────────────────

def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from text."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text


def _extract_frontmatter(text: str) -> dict[str, str]:
    """Extract frontmatter fields as a dict."""
    result: dict[str, str] = {}
    if not text.startswith("---"):
        return result
    parts = text.split("---", 2)
    if len(parts) < 3:
        return result
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip().lower()] = value.strip().strip("\"'")
    return result


# ── HTML escaping ─────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ── Inline Markdown parsing ──────────────────────────────────────────────────

def _parse_inline(text: str) -> str:
    """Convert inline Markdown elements to styled HTML.

    Handles: **bold**, *italic*, `code`, [link](url), ![img](url), ~~del~~
    """
    # Images: ![alt](url "title")
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)",
        lambda m: (
            f'<figure style="{_s("figure")}">'
            f'<img src="{m.group(2)}" alt="{_esc(m.group(1))}" style="{_s("img")}"/>'
            + (f'<figcaption style="{_s("figcaption")}">{_esc(m.group(3))}</figcaption>' if m.group(3) else "")
            + "</figure>"
        ),
        text,
    )

    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{m.group(2)}" style="{_s("a")}">{m.group(1)}</a>',
        text,
    )

    # Bold: **text** or __text__
    text = re.sub(
        r"\*\*(.+?)\*\*|__(.+?)__",
        lambda m: f'<strong style="{_s("strong")}">{m.group(1) or m.group(2)}</strong>',
        text,
    )

    # Italic: *text* or _text_ (but not ** or __)
    text = re.sub(
        r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)",
        lambda m: f'<em style="{_s("em")}">{m.group(1) or m.group(2)}</em>',
        text,
    )

    # Strikethrough: ~~text~~
    text = re.sub(
        r"~~(.+?)~~",
        lambda m: f"<del>{m.group(1)}</del>",
        text,
    )

    # Inline code: `code`
    text = re.sub(
        r"`([^`]+)`",
        lambda m: f'<code style="{_s("code_inline")}">{_esc(m.group(1))}</code>',
        text,
    )

    return text


# ── Block-level Markdown parsing ─────────────────────────────────────────────

def _render_table(lines: list[str]) -> str:
    """Render a Markdown table to styled HTML."""
    if len(lines) < 2:
        return ""

    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:  # skip separator line
        cols = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cols)

    header_html = "".join(
        f'<th style="{_s("th")}">{_parse_inline(h)}</th>' for h in headers
    )
    body_html = ""
    for row in rows:
        cells = "".join(
            f'<td style="{_s("td")}">{_parse_inline(c)}</td>' for c in row
        )
        body_html += f"<tr>{cells}</tr>"

    return (
        f'<section style="{_s("table_section")}">'
        f'<table style="{_s("table")}">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        f"</table></section>"
    )


def _render_code_block(lang: str, code_lines: list[str]) -> str:
    """Render a fenced code block to styled HTML."""
    code_text = _esc("\n".join(code_lines))
    lang_label = f'<span style="position: absolute; top: 0; right: 0; color: #999; font-size: 0.75em; padding: 4px 8px;">{_esc(lang)}</span>' if lang else ""
    return (
        f'<pre style="{_s("code_block")}; position: relative;">'
        f"{lang_label}"
        f'<code style="{_s("code_block_code")}">{code_text}</code>'
        f"</pre>"
    )


def _parse_blocks(text: str) -> str:
    """Parse block-level Markdown into styled HTML."""
    lines = text.split("\n")
    html_parts: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Empty line
        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            html_parts.append(_render_code_block(lang, code_lines))
            continue

        # Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            content = _parse_inline(heading_match.group(2))
            tag = f"h{level}"
            html_parts.append(f'<{tag} style="{_s(tag)}">{content}</{tag}>')
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            html_parts.append(f'<hr style="{_s("hr")}"/>')
            i += 1
            continue

        # Table (starts with |)
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            html_parts.append(_render_table(table_lines))
            continue

        # Blockquote
        if stripped.startswith(">"):
            bq_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                bq_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            bq_content = "\n".join(bq_lines)
            inner = _parse_inline(bq_content)
            html_parts.append(
                f'<blockquote style="{_s("blockquote")}">'
                f'<p style="{_s("blockquote_p")}">{inner}</p>'
                f"</blockquote>"
            )
            continue

        # Unordered list
        if re.match(r"^[-*+]\s+", stripped):
            list_items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                item_text = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                list_items.append(f'<li style="{_s("li")}">• {_parse_inline(item_text)}</li>')
                i += 1
            html_parts.append(f'<ul style="{_s("ul")}">{"".join(list_items)}</ul>')
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            list_items_ol: list[str] = []
            counter = 1
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                item_text = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                list_items_ol.append(
                    f'<li style="{_s("li")}">{counter}. {_parse_inline(item_text)}</li>'
                )
                counter += 1
                i += 1
            html_parts.append(f'<ol style="{_s("ol")}">{"".join(list_items_ol)}</ol>')
            continue

        # Regular paragraph (collect consecutive non-empty lines)
        para_lines: list[str] = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i].strip()):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            para_text = " ".join(para_lines)
            html_parts.append(f'<p style="{_s("p")}">{_parse_inline(para_text)}</p>')
            continue

        i += 1

    return "\n".join(html_parts)


def _is_block_start(line: str) -> bool:
    """Check if a line starts a new block element."""
    if line.startswith("#"):
        return True
    if line.startswith("```"):
        return True
    if line.startswith(">"):
        return True
    if line.startswith("|"):
        return True
    if re.match(r"^[-*+]\s+", line):
        return True
    if re.match(r"^\d+\.\s+", line):
        return True
    if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line):
        return True
    return False


# ── Public API ────────────────────────────────────────────────────────────────

def md_to_wechat_html(
    source: Path,
    *,
    primary_color: str = PRIMARY_COLOR,
    font_size: str = "16px",
) -> tuple[str, dict[str, str]]:
    """Convert a Markdown file to WeChat-compatible HTML with inline styles.

    Args:
        source: Path to the Markdown file.
        primary_color: Theme primary color (default: classic blue).
        font_size: Base font size (default: 16px).

    Returns:
        A tuple of (html_string, frontmatter_dict).
    """
    raw = source.read_text(encoding="utf-8")
    fm = _extract_frontmatter(raw)
    body = _strip_frontmatter(raw)

    # Allow custom primary color override
    if primary_color != PRIMARY_COLOR:
        _update_primary_color(primary_color)

    content_html = _parse_blocks(body)

    # Wrap in container section
    full_html = f'<section style="{_s("container")}">{content_html}</section>'

    return full_html, fm


def _update_primary_color(color: str) -> None:
    """Update the primary color in all style definitions."""
    global STYLES  # noqa: PLW0603
    for key in STYLES:
        STYLES[key] = STYLES[key].replace(PRIMARY_COLOR, color)
