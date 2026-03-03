"""WeChat Official Account publisher via Playwright RPA.

Automates the mp.weixin.qq.com admin website to:
1. Login (QR scan first time, reuse saved cookies afterwards)
2. Navigate to article editor
3. Set title and paste rich HTML content
4. Save as draft or publish directly

Cookie persistence: cookies are saved to ~/.fgeo/wechat/cookies.json
so the user only needs to scan the QR code once per session.

Requires: ``pip install fgeo[publish]`` (playwright + httpx)

Usage::

    from fgeo.publishers.wechat import publish_to_wechat

    result = publish_to_wechat(
        title="My Article",
        html_content="<section>...</section>",
    )
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

# Cookie storage for persistent login
WECHAT_DATA_DIR = Path.home() / ".fgeo" / "wechat"
COOKIES_FILE = WECHAT_DATA_DIR / "cookies.json"

# WeChat MP URLs
MP_BASE = "https://mp.weixin.qq.com"
MP_LOGIN = f"{MP_BASE}/cgi-bin/loginpage"
MP_HOME = f"{MP_BASE}/cgi-bin/home"
MP_ARTICLE_CREATE = f"{MP_BASE}/cgi-bin/appmsg"


def _ensure_data_dir() -> None:
    """Create the WeChat data directory if it doesn't exist."""
    WECHAT_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save_cookies(cookies: list[dict]) -> None:
    """Save browser cookies to disk for session reuse."""
    _ensure_data_dir()
    COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[dim]Cookies saved to {COOKIES_FILE}[/dim]")


def _load_cookies() -> list[dict] | None:
    """Load saved cookies from disk, or None if not available."""
    if COOKIES_FILE.exists():
        try:
            cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
            if isinstance(cookies, list) and cookies:
                return cookies
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _check_playwright() -> None:
    """Check that playwright is installed and browsers are available."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        console.print(
            "[red]playwright not installed.[/red]\n"
            "Run: [bold]pip install fgeo\\[publish][/bold]\n"
            "Then: [bold]playwright install chromium[/bold]"
        )
        raise SystemExit(1)


def _login_with_qr(page: Any) -> bool:
    """Handle WeChat MP QR code login.

    Opens the login page and waits for the user to scan the QR code
    with their WeChat mobile app. Returns True if login succeeds.
    """
    console.print("[bold]WeChat MP login required.[/bold]")
    console.print("Please scan the QR code in the browser window with your WeChat app.")
    console.print("[dim]Waiting for login... (timeout: 120s)[/dim]")

    page.goto(MP_LOGIN, wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Wait for redirect to home page after QR scan (up to 120s)
    try:
        page.wait_for_url("**/cgi-bin/home**", timeout=120000)
        console.print("[green]✓ Login successful![/green]")
        return True
    except Exception:
        console.print("[red]✗ Login timed out. Please try again.[/red]")
        return False


def _is_logged_in(page: Any) -> bool:
    """Check if we're currently logged in by visiting the home page."""
    try:
        page.goto(MP_HOME, wait_until="networkidle", timeout=15000)
        time.sleep(1)
        # If we're redirected to login page, we're not logged in
        current_url = page.url
        return "loginpage" not in current_url and "login" not in current_url
    except Exception:
        return False


def _navigate_to_editor(page: Any) -> bool:
    """Navigate to the article creation editor.

    Returns True if the editor is ready for input.
    """
    # Go to article creation page
    # mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77
    editor_url = f"{MP_BASE}/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77"
    try:
        page.goto(editor_url, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        return True
    except Exception as exc:
        console.print(f"[red]Failed to navigate to editor:[/red] {exc}")
        return False


_CLIPBOARD_PASTE_JS = """
(el, html) => {
    // Clear existing content
    el.innerHTML = '';

    // Use ClipboardEvent paste — reliable for ProseMirror / Quill / Draft.js
    // Technique learned from doocs/cose (Create Once, Sync Everywhere)
    try {
        const dt = new DataTransfer();
        dt.setData('text/html', html);
        dt.setData('text/plain', el.innerText || '');
        const event = new ClipboardEvent('paste', {
            bubbles: true,
            cancelable: true,
            clipboardData: dt,
        });
        const handled = !el.dispatchEvent(event);
        // If the editor consumed the paste event, we're done
        if (handled || el.innerHTML.length > 10) {
            return 'paste';
        }
    } catch (_) {
        // DataTransfer may not be constructible in some contexts
    }

    // Fallback: direct innerHTML assignment
    el.innerHTML = html;
    // Trigger input event so editor framework notices the change
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return 'innerHTML';
}
""".strip()


def _fill_article(page: Any, title: str, html_content: str, author: str = "", digest: str = "") -> bool:
    """Fill in the article editor with title, content, and metadata.

    Uses ClipboardEvent paste for HTML content to work cleanly with
    ProseMirror / UEditor rich-text editors, with innerHTML as fallback.
    Returns True if all fields were set successfully.
    """
    try:
        # Set title
        console.print("[dim]Setting article title...[/dim]")
        title_input = page.locator("#title")
        title_input.wait_for(state="visible", timeout=10000)
        title_input.fill(title)
        time.sleep(0.5)

        # Set author if provided
        if author:
            try:
                author_input = page.locator("#author")
                if author_input.is_visible():
                    author_input.fill(author)
                    time.sleep(0.3)
            except Exception:
                pass  # Author field may not be visible

        # Set content via the rich editor
        # WeChat MP editor uses an editable iframe/div for rich content
        console.print("[dim]Inserting article content via ClipboardEvent paste...[/dim]")

        injection_method: str | None = None

        # Strategy 1: iframe-based UEditor (#ueditor_0)
        try:
            frame_locator = page.frame_locator("#ueditor_0")
            editor_body = frame_locator.locator("body")
            editor_body.wait_for(state="visible", timeout=5000)
            injection_method = editor_body.evaluate(
                _CLIPBOARD_PASTE_JS,
                html_content,
            )
        except Exception:
            pass

        # Strategy 2: div-based editor (ProseMirror / contenteditable)
        if injection_method is None:
            try:
                editor_div = page.locator(
                    ".ProseMirror, .edui-body-container, [contenteditable='true']"
                ).first
                editor_div.wait_for(state="visible", timeout=5000)
                injection_method = editor_div.evaluate(
                    _CLIPBOARD_PASTE_JS,
                    html_content,
                )
            except Exception as exc:
                console.print(f"[red]Failed to find editor element:[/red] {exc}")
                return False

        time.sleep(1)
        console.print(f"[dim]Content injected via {injection_method}[/dim]")

        # Set digest (摘要) if provided
        if digest:
            try:
                digest_input = page.locator("textarea.weui-desktop-form__textarea").first
                if digest_input.is_visible():
                    digest_input.fill(digest)
            except Exception:
                pass

        console.print("[green]✓ Article content inserted[/green]")
        return True

    except Exception as exc:
        console.print(f"[red]Failed to fill article:[/red] {exc}")
        return False


def _save_draft(page: Any) -> str:
    """Click the save draft button and return any confirmation URL.

    Returns the draft URL or empty string.
    """
    try:
        # Look for the save/draft button
        save_btn = page.locator("button:has-text('保存'), a:has-text('保存草稿')").first
        if save_btn.is_visible():
            save_btn.click()
            time.sleep(3)
            console.print("[green]✓ Draft saved[/green]")
        return page.url
    except Exception as exc:
        console.print(f"[yellow]Could not auto-save draft:[/yellow] {exc}")
        return ""


def publish_to_wechat(
    title: str,
    html_content: str,
    *,
    author: str = "",
    digest: str = "",
    headless: bool = False,
    save_only: bool = True,
    task_dir: Path | None = None,
) -> dict[str, str]:
    """Publish or save-as-draft an article to WeChat MP via Playwright RPA.

    Args:
        title: Article title.
        html_content: Full HTML content with inline styles (from wechat_html converter).
        author: Author name (optional).
        digest: Article digest/summary (optional).
        headless: Run browser in headless mode (False for QR login).
        save_only: If True, save as draft only (don't publish). Default True.
        task_dir: Optional directory to save the HTML file for reference.

    Returns:
        A dict with keys: status, url, message.
    """
    _check_playwright()

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    result = {"status": "failed", "url": "", "message": ""}

    # Save HTML to task dir for reference
    if task_dir:
        task_dir.mkdir(parents=True, exist_ok=True)
        html_file = task_dir / "article.html"
        html_file.write_text(html_content, encoding="utf-8")

    with sync_playwright() as p:
        # Always launch headed for QR login; can switch to headless after cookies
        saved_cookies = _load_cookies()
        launch_headless = headless and saved_cookies is not None

        browser = p.chromium.launch(headless=launch_headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Restore saved cookies if available
        if saved_cookies:
            context.add_cookies(saved_cookies)
            console.print("[dim]Restored saved cookies[/dim]")

        page = context.new_page()

        try:
            # Check if we're logged in
            if not _is_logged_in(page):
                if launch_headless:
                    # Need QR scan — must relaunch in headed mode
                    browser.close()
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 900},
                    )
                    page = context.new_page()

                if not _login_with_qr(page):
                    result["message"] = "Login failed or timed out"
                    return result

                # Save cookies after successful login
                _save_cookies(context.cookies())

            # Navigate to article editor
            if not _navigate_to_editor(page):
                result["message"] = "Failed to navigate to editor"
                return result

            # Fill article content
            if not _fill_article(page, title, html_content, author, digest):
                result["message"] = "Failed to insert article content"
                return result

            # Save as draft (default and safest option)
            url = _save_draft(page)

            result["status"] = "draft_saved"
            result["url"] = url
            result["message"] = "Article saved as draft in WeChat MP"

            if not save_only:
                # TODO: Implement direct publish click flow
                # For now, always save as draft — user can publish from MP admin
                console.print(
                    "[yellow]Direct publish not yet supported.[/yellow] "
                    "Article saved as draft. Please publish from mp.weixin.qq.com."
                )

            # Keep browser open briefly for user to verify
            console.print("[dim]Waiting 3s for verification...[/dim]")
            time.sleep(3)

            # Save updated cookies
            _save_cookies(context.cookies())

        except Exception as exc:
            result["message"] = f"Unexpected error: {exc}"
            console.print(f"[red]Error during WeChat publish:[/red] {exc}")

        finally:
            browser.close()

    return result
