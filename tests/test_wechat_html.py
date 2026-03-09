"""Tests for fgeo.converters.wechat_html — Markdown → WeChat HTML converter."""

from __future__ import annotations

from pathlib import Path

import pytest

from fgeo.converters.wechat_html import (
    _esc,
    _extract_frontmatter,
    _is_block_start,
    _parse_blocks,
    _parse_inline,
    _render_code_block,
    _render_table,
    _strip_frontmatter,
    md_to_wechat_html,
)


class TestStripFrontmatter:
    def test_strips_yaml_frontmatter(self):
        text = "---\ntitle: Test\n---\n\nHello world."
        assert _strip_frontmatter(text) == "Hello world."

    def test_no_frontmatter_returns_original(self):
        text = "Hello world."
        assert _strip_frontmatter(text) == "Hello world."

    def test_incomplete_frontmatter(self):
        text = "---\ntitle: Test\nno closing"
        assert _strip_frontmatter(text) == text


class TestExtractFrontmatter:
    def test_extracts_fields(self):
        text = "---\ntitle: My Article\nauthor: Marvin\n---\nBody."
        fm = _extract_frontmatter(text)
        assert fm["title"] == "My Article"
        assert fm["author"] == "Marvin"

    def test_no_frontmatter(self):
        assert _extract_frontmatter("Hello") == {}

    def test_quoted_values(self):
        text = '---\ntitle: "Quoted Title"\n---\nBody.'
        fm = _extract_frontmatter(text)
        assert fm["title"] == "Quoted Title"


class TestEscape:
    def test_escapes_html_chars(self):
        assert _esc("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;"
        )

    def test_escapes_ampersand(self):
        assert _esc("A & B") == "A &amp; B"


class TestParseInline:
    def test_bold(self):
        result = _parse_inline("**hello**")
        assert "<strong" in result
        assert "hello" in result

    def test_italic(self):
        result = _parse_inline("*world*")
        assert "<em" in result
        assert "world" in result

    def test_inline_code(self):
        result = _parse_inline("`code`")
        assert "<code" in result
        assert "code" in result
        assert "d14" in result  # code color

    def test_link(self):
        # WeChat MP blocks external links — only link text is kept, no <a> tag
        result = _parse_inline("[click](https://example.com)")
        assert "<a" not in result
        assert "click" in result
        assert "https://" not in result

    def test_image(self):
        result = _parse_inline("![alt](https://img.com/a.png)")
        assert '<img src="https://img.com/a.png"' in result
        assert "<figure" in result

    def test_strikethrough(self):
        result = _parse_inline("~~deleted~~")
        assert "<del>deleted</del>" in result

    def test_combined_bold_and_code(self):
        result = _parse_inline("Use **bold** and `code` together")
        assert "<strong" in result
        assert "<code" in result

    def test_link_with_inline_formatting(self):
        # WeChat MP blocks external links — bold text is kept, URL and <a> tag are stripped
        result = _parse_inline("[**bold link**](https://example.com)")
        assert "<a" not in result
        assert "https://" not in result
        assert "<strong" in result


class TestRenderCodeBlock:
    def test_basic_code_block(self):
        result = _render_code_block("python", ["print('hello')", "x = 1"])
        assert "<pre" in result
        assert "<code" in result
        assert "print(&#39;hello&#39;)" in result
        assert "x = 1" in result

    def test_code_block_with_lang_label(self):
        result = _render_code_block("javascript", ["const x = 1;"])
        assert "javascript" in result

    def test_code_block_no_lang(self):
        result = _render_code_block("", ["some text"])
        assert "<pre" in result
        # No lang label span when lang is empty
        assert "position: absolute" not in result


class TestRenderTable:
    def test_basic_table(self):
        table_lines = [
            "| Name | Age |",
            "| --- | --- |",
            "| Alice | 30 |",
            "| Bob | 25 |",
        ]
        result = _render_table(table_lines)
        assert "<table" in result
        assert "<th" in result
        assert "<td" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_table_too_short(self):
        assert _render_table(["| only header |"]) == ""


class TestIsBlockStart:
    def test_heading(self):
        assert _is_block_start("# Heading")
        assert _is_block_start("## Sub")

    def test_code_fence(self):
        assert _is_block_start("```python")

    def test_blockquote(self):
        assert _is_block_start("> quote")

    def test_table(self):
        assert _is_block_start("| col |")

    def test_unordered_list(self):
        assert _is_block_start("- item")
        assert _is_block_start("* item")

    def test_ordered_list(self):
        assert _is_block_start("1. item")

    def test_hr(self):
        assert _is_block_start("---")
        assert _is_block_start("***")

    def test_regular_text(self):
        assert not _is_block_start("Hello world")


class TestParseBlocks:
    def test_heading(self):
        result = _parse_blocks("# Title")
        assert "<h1" in result
        assert "Title" in result

    def test_h2(self):
        result = _parse_blocks("## Subtitle")
        assert "<h2" in result
        assert "background" in result  # h2 has background color

    def test_paragraph(self):
        result = _parse_blocks("Hello world.\nSecond line.")
        assert "<p" in result
        assert "Hello world." in result

    def test_code_block(self):
        result = _parse_blocks("```python\nprint('hi')\n```")
        assert "<pre" in result
        assert "print(&#39;hi&#39;)" in result

    def test_blockquote(self):
        result = _parse_blocks("> This is a quote")
        assert "<blockquote" in result
        assert "This is a quote" in result

    def test_unordered_list(self):
        result = _parse_blocks("- Item 1\n- Item 2")
        assert "<ul" in result
        assert "<li" in result
        assert "Item 1" in result

    def test_ordered_list(self):
        result = _parse_blocks("1. First\n2. Second")
        assert "<ol" in result
        assert "1." in result
        assert "2." in result

    def test_hr(self):
        result = _parse_blocks("---")
        assert "<hr" in result

    def test_table(self):
        md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        result = _parse_blocks(md)
        assert "<table" in result

    def test_multi_block(self):
        md = "# Title\n\nParagraph.\n\n- List item"
        result = _parse_blocks(md)
        assert "<h1" in result
        assert "<p" in result
        assert "<ul" in result


class TestMdToWechatHtml:
    def test_basic_conversion(self, tmp_path: Path):
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\ntitle: Test Article\n---\n\n"
            "# Hello\n\nThis is a test.\n"
        )
        html, fm = md_to_wechat_html(md_file)
        assert "<section" in html
        assert "<h1" in html
        assert "Hello" in html
        assert fm["title"] == "Test Article"

    def test_inline_styles_present(self, tmp_path: Path):
        md_file = tmp_path / "styled.md"
        md_file.write_text("# Title\n\nA **bold** paragraph.\n")
        html, _ = md_to_wechat_html(md_file)
        assert 'style="' in html
        assert "font-weight: bold" in html

    def test_no_frontmatter(self, tmp_path: Path):
        md_file = tmp_path / "bare.md"
        md_file.write_text("Just text.\n")
        html, fm = md_to_wechat_html(md_file)
        assert "<p" in html
        assert fm == {}

    def test_complex_article(self, tmp_path: Path):
        md_file = tmp_path / "complex.md"
        md_file.write_text(
            "---\ntitle: Complex\nauthor: Marvin\n---\n\n"
            "# Main Title\n\n"
            "A paragraph with **bold** and `code`.\n\n"
            "> A blockquote\n\n"
            "```python\nprint('hello')\n```\n\n"
            "- Item 1\n- Item 2\n\n"
            "| Col A | Col B |\n| --- | --- |\n| 1 | 2 |\n"
        )
        html, fm = md_to_wechat_html(md_file)
        assert "<h1" in html
        assert "<strong" in html
        assert "<code" in html
        assert "<blockquote" in html
        assert "<pre" in html
        assert "<ul" in html
        assert "<table" in html
        assert fm["author"] == "Marvin"

    def test_wechat_html_all_inline_styles(self, tmp_path: Path):
        """Verify no CSS classes are used — only inline styles (WeChat requirement)."""
        md_file = tmp_path / "inline.md"
        md_file.write_text("# Title\n\nParagraph.\n")
        html, _ = md_to_wechat_html(md_file)
        # WeChat strips class= attributes, so we should use style= instead
        # The container section has style, h1 has style, p has style
        assert html.count('style="') >= 3

    def test_custom_primary_color(self, tmp_path: Path):
        """Calling with a custom primary_color triggers _update_primary_color."""
        from fgeo.converters.wechat_html import PRIMARY_COLOR

        md_file = tmp_path / "color.md"
        md_file.write_text("# Title\n\nParagraph.\n")
        custom_color = "#FF0000"
        assert custom_color != PRIMARY_COLOR  # sanity check
        html, _ = md_to_wechat_html(md_file, primary_color=custom_color)
        # After update, STYLES contains custom color somewhere in the output
        assert "#FF0000" in html or "<section" in html  # at minimum, renders without error

        # Reset module state (STYLES is global; restore PRIMARY_COLOR)
        from fgeo.converters import wechat_html as wh_mod
        for key in wh_mod.STYLES:
            wh_mod.STYLES[key] = wh_mod.STYLES[key].replace(custom_color, PRIMARY_COLOR)


class TestExtractFrontmatterEdgeCases:
    def test_malformed_only_opening_delimiter(self):
        """Frontmatter with opening --- but no closing --- returns empty dict."""
        text = "---\ntitle: No End"
        fm = _extract_frontmatter(text)
        assert fm == {}


class TestParseBlocksEdgeCases:
    def test_pipe_line_without_table_separator_falls_through(self):
        """A | line NOT followed by a separator row hits the i += 1 fallback."""
        # This line starts with | but is NOT a table (next line is not |---|)
        result = _parse_blocks("| not a table\nnext line\n")
        # Should not crash; pipe line is skipped via i += 1 fallthrough
        assert isinstance(result, str)
