"""掘金沸点 (Juejin Pin) publisher via Playwright RPA.

Reuses the same cookie session as the 掘金 article publisher
(~/.fgeo/juejin/cookies.json).  No new login flow is needed if the user
has already set up 掘金 article publishing.

Flow:
  1. Load saved cookies from ~/.fgeo/juejin/cookies.json.
  2. If no cookies or session expired, open headed browser for login.
  3. Navigate to https://juejin.cn/pins.
  4. Type the pin text into the rich-editor contenteditable div.
  5. Intercept the publish API response to capture the pin ID.
  6. Click the publish button (.btn_box button:last).
  7. Return the pin URL: https://juejin.cn/pin/{pin_id}.

Maximum length: 1000 characters (Unicode chars).

Usage::

    from fgeo.publishers.juejin_pin import publish_juejin_pin

    result = publish_juejin_pin("Hello 掘金沸点!")
    # result = {"status": "published" | "failed", "url": "https://juejin.cn/pin/xxx",
    #           "id": "xxx", "message": ""}
"""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console

from fgeo.publishers.juejin import (
    JUEJIN_BASE,
    JUEJIN_LOGIN_URL,
    _check_playwright,
    _clear_cookies,
    _ensure_data_dir,
    _is_logged_in,
    _load_cookies,
    _save_cookies,
)

console = Console()

# ── Constants ─────────────────────────────────────────────────────────────────

JUEJIN_PINS_URL = f"{JUEJIN_BASE}/pins"
JUEJIN_PIN_MAX_CHARS = 1000


# ── Internal helpers ──────────────────────────────────────────────────────────


def _post_pin_playwright(cookies: list[dict] | None, text: str) -> dict[str, Any]:
    """Post a pin to 掘金沸点 via Playwright browser automation.

    If *cookies* is None, performs login in a headed browser first, then
    navigates to the pin editor in the **same** browser session — avoiding
    the cookie-replay race condition that occurs when reopening headless.

    Returns:
        The ``data`` dict from the Juejin API response (may be empty on failure).
    """
    _check_playwright()
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    captured: dict[str, Any] = {}

    def _on_response(response: Any) -> None:
        """Capture the first successful pin-creation API response."""
        if captured or response.status >= 400:
            return
        try:
            body = response.json()
            # Juejin uses err_no=0 for success; data holds the pin payload.
            if body.get("err_no") == 0 and body.get("data"):
                captured.update(body["data"])
        except Exception:
            pass

    needs_login = not cookies

    # Always launch headed — the 掘金 Vue SPA rich editor does not render in
    # headless Chromium (even with valid cookies).
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        page.on("response", _on_response)

        if needs_login:
            _ensure_data_dir()
            console.print("[bold yellow]Not logged in to 掘金 (Juejin).[/bold yellow]")
            console.print("Opening the Juejin login page in your browser…")
            console.print("[dim]Please log in, then come back here and press Enter.[/dim]")
            page.goto(JUEJIN_LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
            input("Press Enter after you have logged in to juejin.cn … ")
            _save_cookies(context.cookies())

        console.print("[dim]Navigating to 掘金沸点 editor…[/dim]")
        page.goto(JUEJIN_PINS_URL, wait_until="networkidle", timeout=30000)

        editor = page.locator("div.rich-editor[contenteditable='true']")
        editor.click()
        page.keyboard.type(text)
        time.sleep(0.5)

        submit = page.locator("div.submit button")
        submit.click()

        # Allow time for the API response to arrive and be processed.
        page.wait_for_timeout(3000)

        browser.close()

    return captured


# ── Public API ────────────────────────────────────────────────────────────────


def publish_juejin_pin(text: str, task_dir=None) -> dict[str, Any]:  # noqa: ARG001
    """Publish a short pin to 掘金沸点 via Playwright RPA.

    Args:
        text: Pin content (max 1000 characters).
        task_dir: Unused — reserved for future logging.

    Returns:
        dict with keys:
            status  : "published" | "failed"
            url     : pin URL (empty on failure)
            id      : pin ID (empty on failure)
            message : error message (empty on success)
    """
    # ── Length validation ─────────────────────────────────────────────────────
    if len(text) > JUEJIN_PIN_MAX_CHARS:
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": (
                f"Content too long: {len(text)} chars "
                f"(max {JUEJIN_PIN_MAX_CHARS})"
            ),
        }

    # ── Cookie auth ───────────────────────────────────────────────────────────
    # Load saved cookies; if expired, clear them and pass None so that login
    # is handled inline inside _post_pin_playwright (same browser session).
    cookies = _load_cookies()
    if cookies and not _is_logged_in(cookies):
        console.print("[yellow]Saved Juejin cookies have expired.[/yellow]")
        _clear_cookies()
        cookies = None

    # ── Post via Playwright ───────────────────────────────────────────────────
    try:
        data = _post_pin_playwright(cookies, text)
    except Exception as exc:
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": f"Browser error: {exc}",
        }

    # Accept any of the known pin ID field names Juejin may return.
    # Juejin 沸点 API uses short_msg_id; fallback to generic *_id scan.
    pin_id = (
        data.get("short_msg_id")
        or data.get("pin_id")
        or data.get("msg_id")
        or data.get("id")
        or next((v for k, v in data.items() if k.endswith("_id") and v), "")
        or ""
    )
    if not pin_id:
        console.print(f"[yellow]API response data: {data}[/yellow]")
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": f"No pin ID in API response (keys: {list(data.keys()) or 'empty'})",
        }

    pin_url = f"{JUEJIN_BASE}/pin/{pin_id}"
    console.print(f"[dim]掘金沸点 published: {pin_url}[/dim]")
    return {
        "status": "published",
        "url": pin_url,
        "id": str(pin_id),
        "message": "",
    }
