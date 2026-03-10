"""掘金沸点 (Juejin Pin) publisher — short-form posts via Cookie auth + REST API.

Reuses the same cookie session as the 掘金 article publisher
(~/.fgeo/juejin/cookies.json).  No new login flow is needed if the user
has already set up 掘金 article publishing.

API used (Juejin internal):
  POST https://api.juejin.cn/euler/server/social_api/v1/pin/create?aid=2608
  Cookie: {browser session cookies}
  Body (JSON): {"content": "...", "topic_ids": [], "pic_list": []}

Response:
  {"err_no": 0, "data": {"pin_id": "...", ...}}

Pin URL: https://juejin.cn/pin/{pin_id}

Maximum length: 1000 characters (counted as Unicode characters, not graphemes).

Usage::

    from fgeo.publishers.juejin_pin import publish_juejin_pin

    result = publish_juejin_pin("Hello 掘金沸点!")
    # result = {"status": "published" | "failed", "url": "https://juejin.cn/pin/xxx",
    #           "id": "xxx", "message": ""}
"""

from __future__ import annotations

from rich.console import Console

from fgeo.publishers.juejin import (
    JUEJIN_AID,
    JUEJIN_API_BASE,
    JUEJIN_BASE,
    _cookies_to_header,
    _get_cookies,
)

console = Console()

# ── Constants ─────────────────────────────────────────────────────────────────

JUEJIN_PIN_MAX_CHARS = 1000
JUEJIN_PIN_API_URL = f"{JUEJIN_API_BASE}/euler/server/social_api/v1/pin/create"


# ── Internal helpers ──────────────────────────────────────────────────────────


def _post_pin(cookies: list[dict], text: str, topic_ids: list | None = None) -> dict:
    """POST a pin to the Juejin API and return the parsed JSON response.

    Raises:
        RuntimeError: if httpx is not installed.
    """
    try:
        import httpx  # noqa: PLC0415
    except ImportError as err:
        raise RuntimeError("httpx not installed — run: pip install httpx") from err

    cookie_header = _cookies_to_header(cookies)
    headers = {
        "Cookie": cookie_header,
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": f"{JUEJIN_BASE}/",
        "Origin": JUEJIN_BASE,
    }
    payload = {
        "content": text,
        "topic_ids": topic_ids or [],
        "pic_list": [],
    }
    params = {"aid": JUEJIN_AID}
    response = httpx.post(
        JUEJIN_PIN_API_URL,
        json=payload,
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# ── Public API ────────────────────────────────────────────────────────────────


def publish_juejin_pin(text: str, task_dir=None) -> dict:
    """Publish a short pin to 掘金沸点.

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
    # ── Dependency check ──────────────────────────────────────────────────────
    try:
        import httpx  # noqa: F401, PLC0415
    except ImportError:
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": "httpx not installed — run: pip install httpx",
        }

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
    cookies = _get_cookies(headless=False)
    if not cookies:
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": "Login failed or cancelled — no cookies obtained",
        }

    # ── API call ──────────────────────────────────────────────────────────────
    try:
        resp = _post_pin(cookies, text)
    except Exception as exc:
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": f"API error: {exc}",
        }

    err_no = resp.get("err_no", -1)
    if err_no != 0:
        err_msg = resp.get("err_msg", "unknown error")
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": f"Juejin API error {err_no}: {err_msg}",
        }

    pin_id = (resp.get("data") or {}).get("pin_id", "")
    if not pin_id:
        return {
            "status": "failed",
            "url": "",
            "id": "",
            "message": "Juejin API returned no pin_id",
        }

    pin_url = f"{JUEJIN_BASE}/pin/{pin_id}"
    console.print(f"[dim]掘金沸点 published: {pin_url}[/dim]")
    return {
        "status": "published",
        "url": pin_url,
        "id": pin_id,
        "message": "",
    }
