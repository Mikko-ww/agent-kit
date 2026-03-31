from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from self_evolve import CONFIG_VERSION, PLUGIN_ID
from self_evolve.jsonc import load_jsonc, write_jsonc
from self_evolve.locale import normalize_language

_EVOLVE_DIR = ".agents/self-evolve"
_SKILL_DIR = ".agents/skills/self-evolve"
_LEGACY_MARKERS = ("learnings", "rules.jsonc")


class LegacyLayoutError(RuntimeError):
    """Raised when a deprecated self-evolve layout is detected."""


@dataclass(slots=True, frozen=True)
class SelfEvolveConfig:
    language: str | None = None
    auto_accept_enabled: bool = False
    auto_accept_min_confidence: float = 0.9
    inline_threshold: int = 20


def evolve_dir(project_root: Path) -> Path:
    return project_root / _EVOLVE_DIR


def config_file_path(project_root: Path) -> Path:
    return evolve_dir(project_root) / "config.jsonc"


def sessions_dir(project_root: Path) -> Path:
    return evolve_dir(project_root) / "sessions"


def candidates_dir(project_root: Path) -> Path:
    return evolve_dir(project_root) / "candidates"


def rules_dir(project_root: Path) -> Path:
    return evolve_dir(project_root) / "rules"


def indexes_dir(project_root: Path) -> Path:
    return evolve_dir(project_root) / "indexes"


def skill_dir(project_root: Path) -> Path:
    return project_root / _SKILL_DIR


def ensure_no_legacy_layout(project_root: Path) -> None:
    base = evolve_dir(project_root)
    for marker in _LEGACY_MARKERS:
        if (base / marker).exists():
            raise LegacyLayoutError("Legacy self-evolve layout detected.")


def find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / _EVOLVE_DIR).is_dir():
            return current
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_config(project_root: Path) -> SelfEvolveConfig | None:
    ensure_no_legacy_layout(project_root)

    path = config_file_path(project_root)
    if not path.exists():
        return None

    data = load_jsonc(path)
    if not isinstance(data, dict):
        return None
    if data.get("config_version") != CONFIG_VERSION:
        raise LegacyLayoutError("Legacy self-evolve config detected.")

    return SelfEvolveConfig(
        language=normalize_language(_optional_str(data.get("language"))),
        auto_accept_enabled=bool(data.get("auto_accept_enabled", False)),
        auto_accept_min_confidence=float(data.get("auto_accept_min_confidence", 0.9)),
        inline_threshold=int(data.get("inline_threshold", 20)),
    )


def save_config(project_root: Path, config: SelfEvolveConfig) -> Path:
    ensure_no_legacy_layout(project_root)
    payload: dict[str, object] = {
        "plugin_id": PLUGIN_ID,
        "config_version": CONFIG_VERSION,
        "auto_accept_enabled": config.auto_accept_enabled,
        "auto_accept_min_confidence": config.auto_accept_min_confidence,
        "inline_threshold": config.inline_threshold,
    }
    if config.language is not None:
        payload["language"] = config.language
    return write_jsonc(config_file_path(project_root), payload)


def resolve_template_language(project_root: Path) -> str:
    config = load_config(project_root)
    if config is not None and config.language is not None:
        return config.language

    env_value = normalize_language(os.environ.get("AGENT_KIT_LANG"))
    if env_value is not None:
        return env_value

    return "en"


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
