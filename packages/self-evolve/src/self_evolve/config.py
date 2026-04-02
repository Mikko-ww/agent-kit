"""配置管理。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from self_evolve import CONFIG_VERSION, PLUGIN_ID
from self_evolve.jsonc import loads_jsonc

_EVOLVE_DIR = ".agents/self-evolve"
_SKILL_DIR = ".agents/skills/self-evolve"


@dataclass(slots=True, frozen=True)
class SelfEvolveConfig:
    language: str | None = None
    inline_threshold: int = 20


def evolve_dir(project_root: Path) -> Path:
    return project_root / _EVOLVE_DIR


def config_file_path(project_root: Path) -> Path:
    return evolve_dir(project_root) / "config.jsonc"


def rules_dir(project_root: Path) -> Path:
    return evolve_dir(project_root) / "rules"


def skill_dir(project_root: Path) -> Path:
    return project_root / _SKILL_DIR


def find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / _EVOLVE_DIR).is_dir() or (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


_CONFIG_HEADER = "// self-evolve configuration\n// JSONC format: comments are preserved on programmatic updates.\n"


def save_config(project_root: Path, config: SelfEvolveConfig) -> Path:
    from self_evolve.jsonc import merge_flat_jsonc

    path = config_file_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "plugin_id": PLUGIN_ID,
        "config_version": CONFIG_VERSION,
        "language": config.language,
        "inline_threshold": config.inline_threshold,
    }

    if path.exists():
        raw = path.read_text(encoding="utf-8")
        content = merge_flat_jsonc(raw, payload)
    else:
        import json
        content = _CONFIG_HEADER + json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    path.write_text(content, encoding="utf-8")
    return path


def load_config(project_root: Path) -> SelfEvolveConfig | None:
    path = config_file_path(project_root)
    if not path.exists():
        return None
    raw = loads_jsonc(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    if raw.get("config_version") != CONFIG_VERSION:
        return None
    return SelfEvolveConfig(
        language=raw.get("language"),
        inline_threshold=int(raw.get("inline_threshold", 20)),
    )


def resolve_template_language(project_root: Path) -> str:
    cfg = load_config(project_root)
    if cfg and cfg.language:
        return cfg.language
    env_lang = os.environ.get("AGENT_KIT_LANG", "")
    if env_lang:
        return env_lang
    return "en"
