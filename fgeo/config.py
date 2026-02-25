"""fgeo config management — read/write ~/.fgeo/config.yaml"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from fgeo.constants import FGEO_CONFIG_FILE


_DEFAULT_CONFIG = {
    "version": "0.1.0",
    "ip": {
        "name": "",
        "slogan": "",
        "tags": [],
    },
    "platforms": {
        "blog": {"enabled": False, "path": ""},
        "twitter": {"enabled": False, "api_key": ""},
        "wechat": {"enabled": False},
        "devto": {"enabled": False, "api_key": ""},
        "medium": {"enabled": False, "api_key": ""},
        "youtube": {"enabled": False, "api_key": ""},
        "bilibili": {"enabled": False},
        "infoq": {"enabled": False},
    },
    "ai": {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key": "",
    },
    "skills": [],
}


def load_config() -> dict[str, Any]:
    if not FGEO_CONFIG_FILE.exists():
        return dict(_DEFAULT_CONFIG)
    with open(FGEO_CONFIG_FILE) as f:
        return yaml.safe_load(f) or dict(_DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    FGEO_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FGEO_CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_default_config() -> dict[str, Any]:
    return dict(_DEFAULT_CONFIG)
