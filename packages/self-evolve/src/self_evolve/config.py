from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from self_evolve import CONFIG_VERSION, PLUGIN_ID
from self_evolve.jsonc import load_jsonc, write_jsonc


@dataclass(slots=True, frozen=True)
class SelfEvolveConfig:
    skills_target_dir: Path
    promotion_threshold: int = 3
    promotion_window_days: int = 30
    min_task_count: int = 2


def config_file_path(config_root: Path) -> Path:
    return config_root / "plugins" / PLUGIN_ID / "config.jsonc"


def load_config(config_root: Path) -> SelfEvolveConfig | None:
    path = config_file_path(config_root)
    if not path.exists():
        return None

    data = load_jsonc(path)
    if not data:
        return None

    if data.get("config_version") != CONFIG_VERSION:
        return None

    skills_target_dir = data.get("skills_target_dir")
    if not skills_target_dir:
        return None

    return SelfEvolveConfig(
        skills_target_dir=Path(skills_target_dir).expanduser(),
        promotion_threshold=int(data.get("promotion_threshold", 3)),
        promotion_window_days=int(data.get("promotion_window_days", 30)),
        min_task_count=int(data.get("min_task_count", 2)),
    )


def save_config(config_root: Path, config: SelfEvolveConfig) -> Path:
    return write_jsonc(
        config_file_path(config_root),
        {
            "plugin_id": PLUGIN_ID,
            "config_version": CONFIG_VERSION,
            "skills_target_dir": str(config.skills_target_dir),
            "promotion_threshold": config.promotion_threshold,
            "promotion_window_days": config.promotion_window_days,
            "min_task_count": config.min_task_count,
        },
    )
