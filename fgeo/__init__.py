"""fgeo — Generative Engine Optimization CLI."""

from __future__ import annotations

try:
    from fgeo._version import version as __version__
except Exception:  # pragma: no cover - source tree fallback before build metadata exists
    __version__ = "0.0.0"
