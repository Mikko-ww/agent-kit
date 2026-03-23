from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from agent_kit.jsonc import load_jsonc, write_jsonc

SUPPORTED_LANGUAGES = ("auto", "en", "zh-CN")
RESOLVED_LANGUAGES = ("en", "zh-CN")


@dataclass(slots=True, frozen=True)
class ResolvedLanguage:
    code: str
    source: str


def resolve_language(*, config_path: Path) -> ResolvedLanguage:
    env_value = normalize_language_preference(os.environ.get("AGENT_KIT_LANG"))
    if env_value in RESOLVED_LANGUAGES:
        return ResolvedLanguage(code=env_value, source="env")

    config_value = normalize_language_preference(load_config_language(config_path))
    if config_value in RESOLVED_LANGUAGES:
        return ResolvedLanguage(code=config_value, source="config")

    system_value = detect_system_language()
    if system_value is not None:
        return ResolvedLanguage(code=system_value, source="system")

    return ResolvedLanguage(code="en", source="default")


def detect_system_language() -> str | None:
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        normalized = normalize_locale_value(os.environ.get(name))
        if normalized is not None:
            return normalized
    return None


def normalize_language_preference(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered == "auto":
        return "auto"
    if lowered == "en":
        return "en"
    if lowered in {"zh-cn", "zh_cn", "zh"}:
        return "zh-CN"
    return None


def normalize_locale_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    base = cleaned.split(".", 1)[0].split("@", 1)[0].replace("_", "-").lower()
    if base.startswith("zh"):
        return "zh-CN"
    if base.startswith("en"):
        return "en"
    return None


def load_config_language(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    try:
        data = load_jsonc(config_path)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return normalize_language_preference(_optional_str(data.get("language")))


def save_config_language(config_path: Path, language: str) -> Path | None:
    existing: dict[str, object] = {}
    if config_path.exists():
        try:
            loaded = load_jsonc(config_path)
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            existing = dict(loaded)

    if language == "auto":
        existing.pop("language", None)
    else:
        existing["language"] = language

    if not existing:
        if config_path.exists():
            config_path.unlink()
        return None

    return write_jsonc(config_path, existing)


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
