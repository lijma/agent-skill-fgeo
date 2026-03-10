"""掘金 (Juejin/Xitu) publisher via browser cookie auth + internal REST API.

Authentication flow (same approach as doocs/cose for Juejin):
  1. First run — launches a headed Chromium browser, user logs in to juejin.cn.
  2. Cookies saved to ~/.fgeo/juejin/cookies.json for subsequent headless runs.
  3. API call to create an article draft via the Juejin internal content API.

API used (Juejin internal, identical to what the web editor sends):
  POST https://api.juejin.cn/content_api/v1/article_draft/create?aid=2608
  Cookie: {browser session cookies}

Draft URL pattern: https://juejin.cn/editor/drafts/{draft_id}

After the user reviews and publishes on juejin.cn, run:
  fgeo publish task done <task_id>

Category IDs (掘金分类，常用):
  后端   : 6809637767543259144  (default)
  前端   : 6809637767543259944
  Android: 6809635626879549454
  iOS    : 6809635626661445640
  工具   : 6809637769959178254
  阅读   : 6809637772874219528

To use a different category, set the platform publish_url field to the category ID:
  fgeo platform set <proj> 掘金 publish_url 6809637767543259944

Usage::

    from fgeo.publishers.juejin import publish_to_juejin

    result = publish_to_juejin(
        title="My Article",
        markdown_content="# Hello\\n\\nBody ...",
        category_id="6809637767543259144",
    )
    # result = {"status": "draft_saved", "url": "https://juejin.cn/editor/drafts/xxx", "id": "xxx"}
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

# ── Paths ─────────────────────────────────────────────────────────────────────

JUEJIN_DATA_DIR = Path.home() / ".fgeo" / "juejin"
COOKIES_FILE = JUEJIN_DATA_DIR / "cookies.json"

# ── Constants ─────────────────────────────────────────────────────────────────

JUEJIN_BASE = "https://juejin.cn"
JUEJIN_API_BASE = "https://api.juejin.cn"
JUEJIN_LOGIN_URL = f"{JUEJIN_BASE}/login"
JUEJIN_AID = "2608"

# Default category: 后端
JUEJIN_DEFAULT_CATEGORY = "6809637767543259144"

# Reference map for agent use (not used in code logic)
JUEJIN_CATEGORIES: dict[str, str] = {
    "后端": "6809637767543259144",
    "前端": "6809637767543259944",
    "Android": "6809635626879549454",
    "iOS": "6809635626661445640",
    "工具": "6809637769959178254",
    "阅读": "6809637772874219528",
}


# ── Cookie helpers ────────────────────────────────────────────────────────────


def _ensure_data_dir() -> None:
    """Create the Juejin data directory if it doesn't exist."""
    JUEJIN_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save_cookies(cookies: list[dict]) -> None:
    """Persist Playwright-format cookies to disk."""
    _ensure_data_dir()
    COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[dim]Juejin cookies saved to {COOKIES_FILE}[/dim]")


def _load_cookies() -> list[dict] | None:
    """Load saved cookies, or None if unavailable/empty."""
    if COOKIES_FILE.exists():
        try:
            cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
            if isinstance(cookies, list) and cookies:
                return cookies
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _clear_cookies() -> None:
    """Delete saved cookies (call when session is known to be expired)."""
    if COOKIES_FILE.exists():
        COOKIES_FILE.unlink()
        console.print("[dim]Stale Juejin cookies cleared.[/dim]")


def _cookies_to_header(cookies: list[dict]) -> str:
    """Convert Playwright-format cookie list to a Cookie header string."""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


# ── Authentication ────────────────────────────────────────────────────────────


def _is_logged_in(cookies: list[dict]) -> bool:
    """Verify saved cookies are still valid via the Juejin user API.

    Returns True if the session is authenticated, False on any error.
    """
    try:
        import httpx  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        return False

    cookie_header = _cookies_to_header(cookies)
    try:
        resp = httpx.get(
            f"{JUEJIN_API_BASE}/user_api/v1/user/get",
            params={"aid": JUEJIN_AID},
            headers={"Cookie": cookie_header},
            timeout=10,
        )
        data = resp.json()
        return bool(data.get("data", {}).get("user_id"))
    except Exception:
        return False


def _check_playwright() -> None:
    """Verify that the playwright package is installed; raise SystemExit if not."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        console.print(
            "[red]playwright not installed.[/red]\n"
            "Run: [bold]pip install fgeo\\[publish] && playwright install chromium[/bold]"
        )
        raise SystemExit(1)


def _do_browser_login() -> list[dict]:
    """Launch a headed Chromium browser and wait for the user to log in to juejin.cn.

    Saves the resulting session cookies to disk and returns them.
    """
    _check_playwright()
    _ensure_data_dir()

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    console.print("[bold yellow]Not logged in to 掘金 (Juejin).[/bold yellow]")
    console.print("Opening the Juejin login page in your browser…")
    console.print("[dim]Please log in, then come back here and press Enter.[/dim]")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(JUEJIN_LOGIN_URL, wait_until="domcontentloaded", timeout=20000)

        input("Press Enter after you have logged in to juejin.cn … ")

        cookies = context.cookies()
        browser.close()

    _save_cookies(cookies)
    return cookies


def _get_cookies() -> list[dict]:
    """Return valid Juejin session cookies, launching browser login if needed."""
    cookies = _load_cookies()
    if cookies:
        if _is_logged_in(cookies):
            return cookies
        console.print("[yellow]Saved Juejin cookies have expired.[/yellow]")
        _clear_cookies()
    return _do_browser_login()


# ── API ───────────────────────────────────────────────────────────────────────


def _create_draft(
    cookies: list[dict],
    title: str,
    markdown_content: str,
    category_id: str,
    tag_ids: list[int],
    brief_content: str = "",
) -> dict[str, Any]:
    """Call the Juejin internal API to create an article draft.

    Raises RuntimeError if httpx is not installed.
    Raises httpx.HTTPStatusError / Exception on network or API errors.
    """
    try:
        import httpx  # noqa: PLC0415
    except ImportError:
        raise RuntimeError("httpx not installed — run: pip install fgeo[publish]")

    cookie_header = _cookies_to_header(cookies)
    request_id = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "category_id": category_id,
        "tag_ids": tag_ids,
        "link_url": "",
        "cover_image": "",
        "title": title,
        "brief_content": brief_content or title,
        "edit_type": 10,       # 10 = Markdown editor
        "html_content": "",    # required by API even when using Markdown
        "mark_content": markdown_content,
        "theme_ids": [],
        "pic_list": [],
    }

    resp = httpx.post(
        f"{JUEJIN_API_BASE}/content_api/v1/article_draft/create",
        json=payload,
        params={"aid": JUEJIN_AID, "uuid": request_id},
        headers={
            "Cookie": cookie_header,
            "Content-Type": "application/json",
            "Origin": JUEJIN_BASE,
            "Referer": f"{JUEJIN_BASE}/editor/drafts/new?v=2",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── Public entry point ────────────────────────────────────────────────────────


def publish_to_juejin(
    title: str,
    markdown_content: str,
    category_id: str = JUEJIN_DEFAULT_CATEGORY,
    tag_ids: list[int] | None = None,
    task_dir: Path | None = None,  # noqa: ARG001  (kept for API consistency)
) -> dict[str, Any]:
    """Publish a Markdown article to 掘金 (Juejin) as a draft.

    Args:
        title: Article title.
        markdown_content: Raw Markdown content (full article body).
        category_id: Juejin category ID (default: 后端).
        tag_ids: Optional list of Juejin numeric tag IDs.
        task_dir: Unused; accepted for API consistency with other publishers.

    Returns:
        dict with keys: status, url, id, message
        status is one of: draft_saved | failed
    """
    try:
        import httpx  # noqa: F401, PLC0415
    except ImportError:
        console.print(
            "[red]httpx not installed.[/red]\n"
            "Run: [bold]pip install fgeo[publish][/bold]"
        )
        return {"status": "failed", "url": "", "id": "", "message": "httpx not installed"}

    console.print("[dim]Authenticating with 掘金…[/dim]")
    try:
        cookies = _get_cookies()
    except Exception as exc:
        return {"status": "failed", "url": "", "id": "", "message": f"Login failed: {exc}"}

    console.print("[dim]Creating 掘金 draft via API…[/dim]")
    try:
        data = _create_draft(
            cookies=cookies,
            title=title,
            markdown_content=markdown_content,
            category_id=category_id,
            tag_ids=tag_ids or [],
        )
    except Exception as exc:
        return {"status": "failed", "url": "", "id": "", "message": str(exc)}

    # Juejin API: {"err_no": 0, "data": {"id": "7xxxxx", ...}}
    err_no = data.get("err_no", -1)
    if err_no != 0:
        err_msg = data.get("err_msg", "unknown error")
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": f"API error {err_no}: {err_msg}",
        }

    draft_id = data.get("data", {}).get("id", "")
    draft_url = f"{JUEJIN_BASE}/editor/drafts/{draft_id}" if draft_id else ""

    console.print(f"[green]掘金 draft created:[/green] {draft_url}")
    return {
        "status": "draft_saved",
        "url": draft_url,
        "id": draft_id,
        "message": "",
    }
