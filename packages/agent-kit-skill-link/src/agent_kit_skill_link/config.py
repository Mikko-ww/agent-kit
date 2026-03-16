from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

import tomli_w

CONFIG_SECTION = "skill_link"


@dataclass(slots=True, frozen=True)
class SkillLinkConfig:
    source_dir: Path
    target_dir: Path


def config_file_path(config_dir: Path) -> Path:
    return config_dir / "config.toml"


def load_config(config_dir: Path) -> SkillLinkConfig | None:
    path = config_file_path(config_dir)
    if not path.exists():
        return None

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    section = data.get(CONFIG_SECTION)
    if not section:
        return None

    source_dir = section.get("source_dir")
    target_dir = section.get("target_dir")
    if not source_dir or not target_dir:
        return None

    return SkillLinkConfig(
        source_dir=Path(source_dir).expanduser(),
        target_dir=Path(target_dir).expanduser(),
    )


def save_config(config_dir: Path, config: SkillLinkConfig) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_file_path(config_dir)
    data: dict[str, object] = {}
    if path.exists():
        data = tomllib.loads(path.read_text(encoding="utf-8"))

    data[CONFIG_SECTION] = {
        "source_dir": str(config.source_dir),
        "target_dir": str(config.target_dir),
    }

    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path
