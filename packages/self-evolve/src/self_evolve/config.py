from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from self_evolve import CONFIG_VERSION, PLUGIN_ID
from self_evolve.jsonc import load_jsonc, write_jsonc

# 支持的 agent target 标识符
SUPPORTED_TARGETS = ("cursor", "copilot", "codex")

# 项目内自我进化数据目录名
EVOLVE_DIR = ".self-evolve"


@dataclass(slots=True, frozen=True)
class SelfEvolveConfig:
    targets: list[str] = field(default_factory=lambda: list(SUPPORTED_TARGETS))
    promotion_threshold: int = 3
    promotion_window_days: int = 30
    min_task_count: int = 2
    auto_promote: bool = False


def evolve_dir(project_root: Path) -> Path:
    return project_root / EVOLVE_DIR


def config_file_path(project_root: Path) -> Path:
    return evolve_dir(project_root) / "config.jsonc"


def find_project_root(start: Path) -> Path | None:
    """从 start 向上查找包含 .self-evolve/ 或 .git/ 的目录。"""
    current = start.resolve()
    while True:
        if (current / EVOLVE_DIR).is_dir():
            return current
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_config(project_root: Path) -> SelfEvolveConfig | None:
    path = config_file_path(project_root)
    if not path.exists():
        return None

    data = load_jsonc(path)
    if not data:
        return None

    if data.get("config_version") != CONFIG_VERSION:
        return None

    raw_targets = data.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        return None

    targets = [str(t) for t in raw_targets if str(t) in SUPPORTED_TARGETS]
    if not targets:
        return None

    return SelfEvolveConfig(
        targets=targets,
        promotion_threshold=int(data.get("promotion_threshold", 3)),
        promotion_window_days=int(data.get("promotion_window_days", 30)),
        min_task_count=int(data.get("min_task_count", 2)),
        auto_promote=bool(data.get("auto_promote", False)),
    )


def save_config(project_root: Path, config: SelfEvolveConfig) -> Path:
    return write_jsonc(
        config_file_path(project_root),
        {
            "plugin_id": PLUGIN_ID,
            "config_version": CONFIG_VERSION,
            "targets": config.targets,
            "promotion_threshold": config.promotion_threshold,
            "promotion_window_days": config.promotion_window_days,
            "min_task_count": config.min_task_count,
            "auto_promote": config.auto_promote,
        },
    )
