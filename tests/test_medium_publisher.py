"""Tests for fgeo.publishers.medium — Playwright RPA publisher (fully mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_page(url: str = "https://medium.com", logged_in: bool = True) -> MagicMock:
    """Return a minimal mock Playwright page."""
    page = MagicMock()
    page.url = url

    # wait_for_selector: succeeds if logged_in, raises if not
    if logged_in:
        page.wait_for_selector.return_value = MagicMock()
    else:
        page.wait_for_selector.side_effect = Exception("Selector not found")

    # locator returns a mock with wait_for, click, evaluate
    locator = MagicMock()
    locator.wait_for.return_value = None
    locator.click.return_value = None
    locator.evaluate.return_value = "paste"
    locator.first = locator
    page.locator.return_value = locator

    return page


# ── _md_to_html ───────────────────────────────────────────────────────────────

class TestMdToHtml:
    def test_paragraph(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("Hello world")
        assert "<p>Hello world</p>" in html

    def test_headings(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("# Title\n## Subtitle")
        assert "<h1>Title</h1>" in html
        assert "<h2>Subtitle</h2>" in html

    def test_bold(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("**bold text**")
        assert "<strong>bold text</strong>" in html

    def test_italic(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("*italic text*")
        assert "<em>italic text</em>" in html

    def test_inline_code(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("`code snippet`")
        assert "<code>code snippet</code>" in html

    def test_code_block(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("```python\nprint('hi')\n```")
        assert "<pre" in html
        assert "<code" in html
        assert "language-python" in html

    def test_mermaid_code_block(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("```mermaid\ngraph LR\nA-->B\n```")
        assert 'class="mermaid"' in html
        assert "<pre" not in html  # mermaid should NOT produce a <pre> block

    def test_unordered_list(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("- item one\n- item two")
        assert "<ul>" in html
        assert "<li>item one</li>" in html
        assert "<li>item two</li>" in html

    def test_ordered_list(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("1. first\n2. second")
        assert "<ol>" in html
        assert "<li>first</li>" in html
        assert "<li>second</li>" in html

    def test_blockquote(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("> A quote here")
        assert "<blockquote>" in html
        assert "A quote here" in html

    def test_horizontal_rule(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("---")
        assert "<hr>" in html

    def test_link(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("[click here](https://example.com)")
        assert 'href="https://example.com"' in html
        assert "click here" in html

    def test_empty_string(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("")
        assert html == ""

    def test_multiple_paragraphs(self):
        from fgeo.publishers.medium import _md_to_html
        html = _md_to_html("First paragraph.\n\nSecond paragraph.")
        assert "<p>First paragraph.</p>" in html
        assert "<p>Second paragraph.</p>" in html

    def test_paragraph_followed_by_heading_no_blank_line(self):
        from fgeo.publishers.medium import _md_to_html
        # Paragraph immediately followed by heading (no blank line) triggers break in para loop
        html = _md_to_html("Some intro text.\n# Heading Without Blank Line")
        assert "Some intro text." in html
        assert "<h1>Heading Without Blank Line</h1>" in html


# ── _inline_md ────────────────────────────────────────────────────────────────

class TestInlineMd:
    def test_bold_double_star(self):
        from fgeo.publishers.medium import _inline_md
        assert "<strong>hello</strong>" in _inline_md("**hello**")

    def test_bold_double_underscore(self):
        from fgeo.publishers.medium import _inline_md
        assert "<strong>hello</strong>" in _inline_md("__hello__")

    def test_italic_star(self):
        from fgeo.publishers.medium import _inline_md
        assert "<em>world</em>" in _inline_md("*world*")

    def test_italic_underscore(self):
        from fgeo.publishers.medium import _inline_md
        assert "<em>world</em>" in _inline_md("_world_")

    def test_inline_code(self):
        from fgeo.publishers.medium import _inline_md
        assert "<code>x</code>" in _inline_md("`x`")

    def test_link(self):
        from fgeo.publishers.medium import _inline_md
        result = _inline_md("[label](http://url.com)")
        assert 'href="http://url.com"' in result
        assert "label" in result

    def test_image_strips_to_alt_text(self):
        from fgeo.publishers.medium import _inline_md
        result = _inline_md("![alt text](image.png)")
        assert "alt text" in result
        assert "image.png" not in result
        assert "<img" not in result

    def test_image_external_png_kept(self):
        from fgeo.publishers.medium import _inline_md
        result = _inline_md("![chart](https://example.com/chart.png)")
        assert "<img" not in result
        assert "chart" in result

    def test_image_kroki_svg_converted_to_png(self):
        from fgeo.publishers.medium import _inline_md
        svg_url = "https://kroki.io/mermaid/svg/abc123"
        result = _inline_md(f"![diagram]({svg_url})")
        assert "<img" not in result
        assert "diagram" in result

    def test_image_generic_svg_url_stripped(self):
        from fgeo.publishers.medium import _inline_md
        result = _inline_md("![diagram](https://example.com/chart.svg)")
        assert "<img" not in result
        assert "diagram" in result

    def test_strikethrough(self):
        from fgeo.publishers.medium import _inline_md
        assert "<s>gone</s>" in _inline_md("~~gone~~")

    def test_plain_text_unchanged(self):
        from fgeo.publishers.medium import _inline_md
        assert _inline_md("plain text") == "plain text"


# ── _strip_frontmatter ────────────────────────────────────────────────────────

class TestStripFrontmatter:
    def test_strips_yaml_header(self):
        from fgeo.publishers.medium import _strip_frontmatter
        md = "---\ntitle: Test\n---\nBody text"
        result = _strip_frontmatter(md)
        assert result == "Body text"

    def test_no_frontmatter_unchanged(self):
        from fgeo.publishers.medium import _strip_frontmatter
        md = "# Just a heading\n\nBody"
        assert _strip_frontmatter(md) == md

    def test_empty_string(self):
        from fgeo.publishers.medium import _strip_frontmatter
        assert _strip_frontmatter("") == ""


# ── _check_playwright ─────────────────────────────────────────────────────────

class TestCheckPlaywright:
    def test_raises_if_playwright_missing(self):
        import sys
        from fgeo.publishers.medium import _check_playwright
        with patch.dict(sys.modules, {"playwright": None}):
            with pytest.raises(SystemExit):
                _check_playwright()

    def test_passes_if_playwright_available(self):
        from fgeo.publishers.medium import _check_playwright
        with patch.dict("sys.modules", {"playwright": MagicMock()}):
            _check_playwright()  # Should not raise


# ── _is_logged_in ────────────────────────────────────────────────────────────

class TestIsLoggedIn:
    def test_returns_true_when_logged_in(self):
        from fgeo.publishers.medium import _is_logged_in
        page = MagicMock()
        page.goto.return_value = None
        page.url = "https://medium.com/me/settings"
        with patch("time.sleep"):
            result = _is_logged_in(page)
        assert result is True

    def test_returns_false_when_redirected_to_signin(self):
        from fgeo.publishers.medium import _is_logged_in
        page = MagicMock()
        page.goto.return_value = None
        page.url = "https://medium.com/m/signin"
        with patch("time.sleep"):
            result = _is_logged_in(page)
        assert result is False

    def test_returns_false_when_page_goto_raises(self):
        from fgeo.publishers.medium import _is_logged_in
        page = MagicMock()
        page.goto.side_effect = Exception("Network error")
        with patch("time.sleep"):
            result = _is_logged_in(page)
        assert result is False

    def test_returns_false_when_redirected_to_login(self):
        from fgeo.publishers.medium import _is_logged_in
        page = MagicMock()
        page.goto.return_value = None
        page.url = "https://medium.com/m/signin"
        with patch("time.sleep"):
            result = _is_logged_in(page)
        assert result is False

    def test_returns_true_when_url_has_source_login_query_param(self):
        """?source=login in query string must NOT be treated as a login page."""
        from fgeo.publishers.medium import _is_logged_in
        page = MagicMock()
        page.goto.return_value = None
        page.url = "https://medium.com/?source=login-abc123"
        with patch("time.sleep"):
            result = _is_logged_in(page)
        assert result is True


# ── _fill_medium_article ──────────────────────────────────────────────────────

class TestFillMediumArticle:
    def test_returns_true_on_success(self):
        from fgeo.publishers.medium import _fill_medium_article
        page = _make_page()
        result = _fill_medium_article(page, "Test Title", "<p>Hello</p>")
        assert result is True

    def test_returns_false_if_title_selector_fails(self):
        from fgeo.publishers.medium import _fill_medium_article
        page = _make_page()
        locator = MagicMock()
        locator.wait_for.side_effect = Exception("Title not found")
        locator.first = locator
        page.locator.return_value = locator
        result = _fill_medium_article(page, "Test Title", "<p>Hello</p>")
        assert result is False

    def test_returns_false_if_body_paste_fails(self):
        from fgeo.publishers.medium import _fill_medium_article
        page = _make_page()
        call_count = [0]
        def make_locator(*args, **kwargs):
            call_count[0] += 1
            loc = MagicMock()
            loc.first = loc
            if call_count[0] == 1:
                # title locator — ok
                loc.wait_for.return_value = None
                loc.evaluate.return_value = None
            else:
                # body locator — fails
                loc.wait_for.side_effect = Exception("Body not found")
            return loc
        page.locator.side_effect = make_locator
        result = _fill_medium_article(page, "Test Title", "<p>Hello</p>")
        assert result is False

    def test_mermaid_content_waits_for_render(self):
        """Content with class="mermaid" triggers the 3-second render wait branch."""
        from fgeo.publishers.medium import _fill_medium_article
        page = _make_page()
        mermaid_html = '<div class="mermaid">graph LR\nA-->B</div>'
        with patch("time.sleep"):
            result = _fill_medium_article(page, "Mermaid Title", mermaid_html)
        assert result is True

    def test_returns_false_if_set_content_raises(self):
        """If page.set_content raises, _fill_medium_article returns False."""
        from fgeo.publishers.medium import _fill_medium_article
        page = _make_page()
        page.set_content.side_effect = Exception("Browser crashed")
        with patch("time.sleep"):
            result = _fill_medium_article(page, "Title", "<p>text</p>")
        assert result is False


# ── _wait_for_login ──────────────────────────────────────────────────────────

class TestWaitForLogin:
    def test_returns_true_when_user_inputs_1(self):
        """User types '1' (already logged in) → True."""
        from fgeo.publishers.medium import _wait_for_login
        page = MagicMock()
        with patch("builtins.input", return_value="1"):
            result = _wait_for_login(page)
        assert result is True

    def test_returns_false_when_user_inputs_2(self):
        """User types '2' (quit) → False."""
        from fgeo.publishers.medium import _wait_for_login
        page = MagicMock()
        with patch("builtins.input", return_value="2"):
            result = _wait_for_login(page)
        assert result is False

    def test_retries_on_invalid_input_then_accepts_1(self):
        """User types garbage, then '1' → True after retry."""
        from fgeo.publishers.medium import _wait_for_login
        page = MagicMock()
        with patch("builtins.input", side_effect=["x", "", "1"]):
            result = _wait_for_login(page)
        assert result is True

    def test_opens_signin_page(self):
        """Browser is navigated to /m/signin before the prompt."""
        from fgeo.publishers.medium import _wait_for_login
        page = MagicMock()
        with patch("builtins.input", return_value="1"):
            _wait_for_login(page)
        page.goto.assert_called_once()
        assert "/m/signin" in page.goto.call_args.args[0]


# ── _wait_for_autosave ────────────────────────────────────────────────────────

class TestWaitForAutosave:
    def test_returns_unique_url_when_saved(self):
        from fgeo.publishers.medium import _wait_for_autosave
        page = MagicMock()
        page.url = "https://medium.com/@user/my-draft-abc123"
        with patch("time.sleep"):
            url = _wait_for_autosave(page, max_wait=1)
        assert "abc123" in url

    def test_returns_current_url_if_no_save_detected(self):
        from fgeo.publishers.medium import _wait_for_autosave
        page = MagicMock()
        page.url = "https://medium.com/new-story"
        with patch("time.sleep"), patch("time.time", side_effect=[0, 0, 1, 2]):
            url = _wait_for_autosave(page, max_wait=1)
        assert "medium.com" in url


# ── publish_to_medium ─────────────────────────────────────────────────────────

# ── _click_publish ────────────────────────────────────────────────────────────

class TestClickPublish:
    def _make_page(self):
        page = MagicMock()
        locator = MagicMock()
        locator.wait_for.return_value = None
        locator.click.return_value = None
        locator.first = locator
        page.locator.return_value = locator
        return page, locator

    def test_returns_true_on_success(self):
        from fgeo.publishers.medium import _click_publish
        page, _ = self._make_page()
        with patch("time.sleep"):
            result = _click_publish(page)
        assert result is True

    def test_returns_false_when_publish_btn_not_found(self):
        from fgeo.publishers.medium import _click_publish
        page = MagicMock()
        locator = MagicMock()
        locator.wait_for.side_effect = Exception("Publish button not found")
        locator.first = locator
        page.locator.return_value = locator
        with patch("time.sleep"):
            result = _click_publish(page)
        assert result is False

    def test_returns_false_when_confirm_btn_not_found(self):
        from fgeo.publishers.medium import _click_publish
        page, _ = self._make_page()
        # The first publish-panel button (page.locator) succeeds;
        # the confirm button uses get_by_role and fails.
        confirm_btn = MagicMock()
        confirm_btn.wait_for.side_effect = Exception("Confirm not found")
        page.get_by_role.return_value = confirm_btn
        with patch("time.sleep"):
            result = _click_publish(page)
        assert result is False

    def test_with_subtitle_fills_subtitle_field(self):
        """Passing subtitle= covers the subtitle-fill branch (L395-402)."""
        from fgeo.publishers.medium import _click_publish
        page, _ = self._make_page()
        with patch("time.sleep"):
            result = _click_publish(page, subtitle="A great subtitle")
        assert result is True

    def test_with_subtitle_handles_exception(self):
        """Subtitle fill that raises logs a warning but does not return False (L403-404)."""
        from fgeo.publishers.medium import _click_publish
        page, _ = self._make_page()
        call_count = [0]

        def make_locator(*args, **kwargs):
            call_count[0] += 1
            loc = MagicMock()
            loc.first = loc
            if call_count[0] == 1:
                loc.wait_for.return_value = None  # publish-panel btn: ok
                loc.click.return_value = None
            else:
                loc.wait_for.side_effect = Exception("Subtitle field not found")
            return loc

        page.locator.side_effect = make_locator
        with patch("time.sleep"):
            result = _click_publish(page, subtitle="My subtitle")
        # subtitle failure is non-fatal — function still returns True
        assert result is True

    def test_with_tags_fills_topic_input(self):
        """Passing tags= covers the tags-fill branch (L408-418)."""
        from fgeo.publishers.medium import _click_publish
        page, _ = self._make_page()
        with patch("time.sleep"):
            result = _click_publish(page, tags=["python", "devto"])
        assert result is True

    def test_with_tags_handles_exception(self):
        """Tags fill that raises logs a warning but does not return False (L419-420)."""
        from fgeo.publishers.medium import _click_publish
        page, _ = self._make_page()
        call_count = [0]

        def make_locator(*args, **kwargs):
            call_count[0] += 1
            loc = MagicMock()
            loc.first = loc
            if call_count[0] == 1:
                loc.wait_for.return_value = None  # publish-panel btn: ok
                loc.click.return_value = None
            else:
                loc.wait_for.side_effect = Exception("Tag input not found")
            return loc

        page.locator.side_effect = make_locator
        with patch("time.sleep"):
            result = _click_publish(page, tags=["python"])
        # tags failure is non-fatal — function still returns True
        assert result is True


# ── publish_to_medium ─────────────────────────────────────────────────────────

class TestPublishToMedium:
    """Tests for publish_to_medium using sys.modules to mock playwright.sync_api."""

    def _make_playwright_mocks(self, draft_url: str = "https://medium.com/@u/draft-abc"):
        """Build mock playwright objects for launch_persistent_context pattern."""
        import sys

        page = _make_page(url=draft_url)
        page.url = draft_url

        context = MagicMock()
        context.new_page.return_value = page

        pw_instance = MagicMock()
        pw_instance.chromium.launch_persistent_context.return_value = context

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=pw_instance)
        cm.__exit__ = MagicMock(return_value=False)

        fake_pw_mod = MagicMock()
        fake_pw_mod.sync_playwright.return_value = cm

        return fake_pw_mod, cm, pw_instance, context, page

    def test_happy_path_returns_published(self, tmp_path):
        import sys
        from fgeo.publishers.medium import publish_to_medium
        draft_url = "https://medium.com/@testuser/my-article-abc"
        fake_pw_mod, cm, pw_instance, context, page = self._make_playwright_mocks(draft_url)

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=True), \
             patch("fgeo.publishers.medium._fill_medium_article", return_value=True), \
             patch("fgeo.publishers.medium._wait_for_autosave", return_value=draft_url), \
             patch("fgeo.publishers.medium._click_publish", return_value=True), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(
                    title="My Article",
                    markdown_content="# Hello\n\nBody text",
                    task_dir=tmp_path,
                )
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "published"

    def test_falls_back_to_draft_when_publish_click_fails(self, tmp_path):
        """If _click_publish returns False, status is 'draft_saved' not 'failed'."""
        import sys
        from fgeo.publishers.medium import publish_to_medium
        draft_url = "https://medium.com/@u/draft-abc"
        fake_pw_mod, *_ = self._make_playwright_mocks(draft_url)

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=True), \
             patch("fgeo.publishers.medium._fill_medium_article", return_value=True), \
             patch("fgeo.publishers.medium._wait_for_autosave", return_value=draft_url), \
             patch("fgeo.publishers.medium._click_publish", return_value=False), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(title="Test", markdown_content="Content", task_dir=tmp_path)
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "draft_saved"
        assert result["url"] == draft_url

    def test_uses_launch_persistent_context_with_fgeo_profile(self, tmp_path):
        """publish_to_medium must use launch_persistent_context with FGEO_CHROME_PROFILE."""
        import sys
        from fgeo.publishers.medium import publish_to_medium
        draft_url = "https://medium.com/@u/draft"
        fake_pw_mod, cm, pw_instance, context, page = self._make_playwright_mocks(draft_url)
        fgeo_profile = tmp_path / "chrome-profile"

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", fgeo_profile), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=True), \
             patch("fgeo.publishers.medium._fill_medium_article", return_value=True), \
             patch("fgeo.publishers.medium._wait_for_autosave", return_value=draft_url), \
             patch("fgeo.publishers.medium._click_publish", return_value=True), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                publish_to_medium(title="Test", markdown_content="Body")
            finally:
                sys.modules.pop("playwright.sync_api", None)

        pw_instance.chromium.launch_persistent_context.assert_called_once()
        call_args = pw_instance.chromium.launch_persistent_context.call_args
        assert call_args.args[0] == str(fgeo_profile)

    def test_saves_article_files_to_task_dir(self, tmp_path):
        import sys
        from fgeo.publishers.medium import publish_to_medium
        draft_url = "https://medium.com/@u/draft"
        fake_pw_mod, *_ = self._make_playwright_mocks(draft_url)

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=True), \
             patch("fgeo.publishers.medium._fill_medium_article", return_value=True), \
             patch("fgeo.publishers.medium._wait_for_autosave", return_value=draft_url), \
             patch("fgeo.publishers.medium._click_publish", return_value=True), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                publish_to_medium(title="Test", markdown_content="Content", task_dir=tmp_path)
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert (tmp_path / "article.md").exists()
        assert (tmp_path / "article.html").exists()

    def test_returns_failed_when_fill_fails(self, tmp_path):
        import sys
        from fgeo.publishers.medium import publish_to_medium
        fake_pw_mod, *_ = self._make_playwright_mocks()

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=True), \
             patch("fgeo.publishers.medium._fill_medium_article", return_value=False), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(title="Test", markdown_content="Content", task_dir=tmp_path)
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "Failed to fill" in result["message"]

    def test_login_prompt_when_not_logged_in(self, tmp_path):
        import sys
        from fgeo.publishers.medium import publish_to_medium
        draft_url = "https://medium.com/@u/draft"
        fake_pw_mod, *_ = self._make_playwright_mocks(draft_url)

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=False), \
             patch("fgeo.publishers.medium._wait_for_login", return_value=True) as mock_login, \
             patch("fgeo.publishers.medium._fill_medium_article", return_value=True), \
             patch("fgeo.publishers.medium._wait_for_autosave", return_value=draft_url), \
             patch("fgeo.publishers.medium._click_publish", return_value=True), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(title="Test", markdown_content="Content")
            finally:
                sys.modules.pop("playwright.sync_api", None)

        mock_login.assert_called_once()
        assert result["status"] == "published"

    def test_returns_failed_when_login_times_out(self, tmp_path):
        import sys
        from fgeo.publishers.medium import publish_to_medium
        fake_pw_mod, *_ = self._make_playwright_mocks()

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=False), \
             patch("fgeo.publishers.medium._wait_for_login", return_value=False), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(title="Test", markdown_content="Content")
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "timed out" in result["message"].lower()

    def test_handles_unexpected_exception(self, tmp_path):
        import sys
        from fgeo.publishers.medium import publish_to_medium
        fake_pw_mod, *_ = self._make_playwright_mocks()

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", side_effect=RuntimeError("boom")), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(title="Test", markdown_content="Content", task_dir=tmp_path)
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "boom" in result["message"]

    def test_keyboard_interrupt_returns_cancelled(self, tmp_path):
        import sys
        from fgeo.publishers.medium import publish_to_medium
        fake_pw_mod, *_ = self._make_playwright_mocks()

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", side_effect=KeyboardInterrupt), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(title="Test", markdown_content="Content", task_dir=tmp_path)
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "failed"
        assert "cancelled" in result["message"].lower()

    def test_context_close_suppresses_target_closed_error(self, tmp_path):
        """TargetClosedError from context.close() in finally is silently suppressed."""
        import sys
        from fgeo.publishers.medium import publish_to_medium
        draft_url = "https://medium.com/@u/draft"
        fake_pw_mod, cm, pw_instance, context, page = self._make_playwright_mocks(draft_url)
        context.close.side_effect = Exception("TargetClosedError")

        with patch("fgeo.publishers.medium._check_playwright"), \
             patch("fgeo.publishers.medium.FGEO_CHROME_PROFILE", tmp_path / "chrome-profile"), \
             patch("fgeo.publishers.medium._is_logged_in", return_value=True), \
             patch("fgeo.publishers.medium._fill_medium_article", return_value=True), \
             patch("fgeo.publishers.medium._wait_for_autosave", return_value=draft_url), \
             patch("fgeo.publishers.medium._click_publish", return_value=True), \
             patch("time.sleep"):
            sys.modules["playwright.sync_api"] = fake_pw_mod
            try:
                result = publish_to_medium(title="Test", markdown_content="Content", task_dir=tmp_path)
            finally:
                sys.modules.pop("playwright.sync_api", None)

        assert result["status"] == "published"
