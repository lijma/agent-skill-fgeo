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
from urllib.parse import parse_qs, urlparse

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


def _clear_cookies() -> None:
    """Delete saved cookies (call when session is known to be expired)."""
    if COOKIES_FILE.exists():
        COOKIES_FILE.unlink()
        console.print("[dim]Stale cookies cleared.[/dim]")


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
    """Check that playwright is installed and browsers are available.

    If the playwright Python package is installed but the Chromium browser
    binary is missing, automatically downloads it via ``playwright install chromium``
    so the user does not need to run it manually.
    """
    try:
        import playwright  # noqa: F401
    except ImportError:
        console.print(
            "[red]playwright not installed.[/red]\n"
            "Run: [bold]pip install fgeo\\[publish][/bold]"
        )
        raise SystemExit(1)

    # Check if Chromium binary is present; auto-install if not.
    try:
        from playwright.sync_api import sync_playwright as _sync_playwright

        with _sync_playwright() as _p:
            _browser_path = Path(_p.chromium.executable_path)
        if not _browser_path.exists():
            _install_playwright_browsers()
    except SystemExit:
        raise
    except Exception:
        pass  # Browser path check failed; let launch() surface the real error.


def _install_playwright_browsers() -> None:
    """Download Playwright browser binaries (chromium only)."""
    import subprocess

    console.print("[yellow]Chromium browser not found — downloading (one-time setup)…[/yellow]")
    result = subprocess.run(["playwright", "install", "chromium"])
    if result.returncode != 0:
        console.print(
            "[red]Failed to install Chromium automatically.[/red]\n"
            "Run manually: [bold]playwright install chromium[/bold]"
        )
        raise SystemExit(1)
    console.print("[green]✓ Chromium installed.[/green]")


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


# Phrases that appear in the page body when the WeChat session has expired.
_SESSION_EXPIRED_TEXTS = [
    "Login timeout",
    "login timeout",
    "请重新登录",
    "登录超时",
    "log in again",
    "Log in again",
]


def _is_logged_in(page: Any) -> bool:
    """Check if we're currently logged in by visiting the home page.

    Checks both the URL (redirect to loginpage) *and* the page body text
    (WeChat sometimes shows a 'Login timeout' message without redirecting).
    """
    try:
        page.goto(MP_HOME, wait_until="networkidle", timeout=15000)
        time.sleep(1)
        current_url = page.url
        if "loginpage" in current_url or "login" in current_url:
            return False
        # Even if URL looks fine, check for in-page session-expired messages
        try:
            body_text = page.inner_text("body", timeout=5000)
            if any(phrase in body_text for phrase in _SESSION_EXPIRED_TEXTS):
                console.print("[yellow]Session expired (detected in page content).[/yellow]")
                return False
        except Exception:
            pass  # Can't read body — assume logged in and let later steps fail naturally
        return True
    except Exception:
        return False


def _extract_token(url: str) -> str:
    """Extract the WeChat MP session token from a URL query string.

    After login, WeChat redirects to a URL like:
      https://mp.weixin.qq.com/cgi-bin/home?t=home/index&token=862082663
    All subsequent page URLs must include this token or the server will
    redirect back to the login page.

    Returns the token string, or empty string if not found.
    """
    try:
        qs = parse_qs(urlparse(url).query)
        return qs.get("token", [""])[0]
    except Exception:
        return ""


def _navigate_to_editor(page: Any, token: str = "") -> bool:
    """Navigate to the article creation editor.

    Args:
        page: Playwright page object.
        token: WeChat MP session token extracted from the post-login URL.
               Must be provided, otherwise the server redirects to login.

    Returns True if the editor loaded successfully.
    """
    if not token:
        console.print("[yellow]No session token available — editor URL may redirect to login.[/yellow]")
    token_param = f"&token={token}" if token else ""
    editor_url = f"{MP_BASE}/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&type=77{token_param}"
    console.print(f"[dim]Navigating to editor (token={'***' if token else 'none'})...[/dim]")
    try:
        page.goto(editor_url, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        # Verify we didn't get redirected back to login
        if "loginpage" in page.url or "login" in page.url:
            console.print("[red]Editor navigation redirected to login — session may have expired.[/red]")
            return False
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
    """Fill in the WeChat MP article editor.

    Selectors confirmed from live DOM (2026-03):
      - Title:   textarea#title
      - Author:  input#author
      - Editor:  #ueditor_0 .ProseMirror[contenteditable="true"]  (mock-iframe div, NOT a real iframe)
      - Digest:  textarea#js_description

    Uses ClipboardEvent paste for HTML content; falls back to innerHTML + input event.
    Returns True if all required fields were set successfully.
    """
    try:
        # ── Title ─────────────────────────────────────────────────────────────
        console.print("[dim]Setting article title...[/dim]")
        title_input = page.locator("textarea#title")
        title_input.wait_for(state="visible", timeout=10000)
        title_input.click()
        title_input.fill(title)
        time.sleep(0.5)

        # ── Author (optional) ─────────────────────────────────────────────────
        if author:
            try:
                author_input = page.locator("#author")
                if author_input.is_visible():
                    author_input.click()
                    author_input.fill(author)
                    time.sleep(0.3)
            except Exception:
                pass

        # ── Content (ProseMirror inside mock-iframe div) ───────────────────────
        # #ueditor_0 is a *div* styled as mock-iframe — page.frame_locator() won't work.
        # Target the ProseMirror contenteditable div directly.
        console.print("[dim]Inserting article content via ClipboardEvent paste...[/dim]")
        try:
            editor = page.locator("#ueditor_0 .ProseMirror[contenteditable='true']")
            editor.wait_for(state="visible", timeout=10000)
            editor.click()  # focus the editor first
            time.sleep(0.3)
            injection_method = editor.evaluate(_CLIPBOARD_PASTE_JS, html_content)
        except Exception as exc:
            console.print(f"[red]Failed to inject content into editor:[/red] {exc}")
            return False

        time.sleep(1)
        console.print(f"[dim]Content injected via {injection_method}[/dim]")

        # ── Digest / 摘要 (optional) ────────────────────────────────────────────
        if digest:
            try:
                digest_input = page.locator("textarea#js_description")
                if digest_input.is_visible():
                    digest_input.click()
                    digest_input.fill(digest)
            except Exception:
                pass

        console.print("[green]✓ Article content inserted[/green]")
        return True

    except Exception as exc:
        console.print(f"[red]Failed to fill article:[/red] {exc}")
        return False


def _save_draft(page: Any) -> str:
    """Click the '保存为草稿' button and return the resulting page URL.

    Confirmed selector from live DOM: #js_submit button
    Returns the URL after saving, or empty string on failure.
    """
    try:
        # #js_submit > button contains the text '保存为草稿'
        save_btn = page.locator("#js_submit button")
        save_btn.wait_for(state="visible", timeout=10000)
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
            # Check if we're logged in (URL + page-content check)
            if not _is_logged_in(page):
                if saved_cookies:
                    # Cookies were stale — remove them so next run starts fresh
                    _clear_cookies()
                    console.print("[yellow]Saved session expired. A new QR login is required.[/yellow]")

                if launch_headless:
                    # QR scan requires a visible browser — relaunch headed
                    browser.close()
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 900},
                    )
                    page = context.new_page()

                if not _login_with_qr(page):
                    result["message"] = "Login failed or timed out"
                    return result

                # Save fresh cookies after successful QR login
                _save_cookies(context.cookies())

            # Extract the session token from the current page URL.
            # WeChat MP requires ?token=XXXXXX on every admin page URL;
            # without it the server redirects back to the login page.
            session_token = _extract_token(page.url)
            if session_token:
                console.print(f"[dim]Session token: {session_token}[/dim]")
            else:
                console.print("[yellow]Could not extract session token from URL — trying without.[/yellow]")

            # Navigate to article editor
            if not _navigate_to_editor(page, token=session_token):
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
