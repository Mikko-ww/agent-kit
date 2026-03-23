from __future__ import annotations

import os
from pathlib import Path

from skills_link.jsonc import load_jsonc


def resolve_language(config_root: Path) -> str:
    env_value = normalize_language(os.environ.get("AGENT_KIT_LANG"))
    if env_value is not None:
        return env_value

    config_path = config_root / "config.jsonc"
    if config_path.exists():
        try:
            data = load_jsonc(config_path)
        except Exception:
            data = None
        if isinstance(data, dict):
            config_value = normalize_language(_optional_str(data.get("language")))
            if config_value is not None:
                return config_value

    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        system_value = normalize_locale(os.environ.get(name))
        if system_value is not None:
            return system_value

    return "en"


def normalize_language(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered == "en":
        return "en"
    if lowered in {"zh", "zh-cn", "zh_cn"}:
        return "zh-CN"
    return None


def normalize_locale(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().split(".", 1)[0].split("@", 1)[0].replace("_", "-").lower()
    if normalized.startswith("zh"):
        return "zh-CN"
    if normalized.startswith("en"):
        return "en"
    return None


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
