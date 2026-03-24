from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from skills_link import CONFIG_VERSION, PLUGIN_ID
from skills_link.jsonc import load_jsonc, write_jsonc

TARGET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(slots=True, frozen=True)
class TargetConfig:
    name: str
    path: Path


@dataclass(slots=True, frozen=True)
class SkillLinkConfig:
    source_dir: Path
    targets: list[TargetConfig]


def config_file_path(config_root: Path) -> Path:
    return config_root / "plugins" / PLUGIN_ID / "config.jsonc"


def load_config(config_root: Path) -> SkillLinkConfig | None:
    path = config_file_path(config_root)
    if not path.exists():
        return None

    data = load_jsonc(path)
    if not data:
        return None

    if data.get("config_version") != CONFIG_VERSION:
        return None

    source_dir = data.get("source_dir")
    targets_data = data.get("targets")
    if not source_dir or not isinstance(targets_data, list) or not targets_data:
        return None

    targets: list[TargetConfig] = []
    seen_names: set[str] = set()
    for item in targets_data:
        if not isinstance(item, dict):
            return None
        name = item.get("name")
        raw_path = item.get("path")
        if not _is_valid_target_name(name) or not raw_path:
            return None
        if name in seen_names:
            return None
        seen_names.add(name)
        targets.append(TargetConfig(name=name, path=Path(raw_path).expanduser()))

    return SkillLinkConfig(
        source_dir=Path(source_dir).expanduser(),
        targets=targets,
    )


def save_config(config_root: Path, config: SkillLinkConfig) -> Path:
    _validate_config(config)
    return write_jsonc(
        config_file_path(config_root),
        {
            "plugin_id": PLUGIN_ID,
            "config_version": CONFIG_VERSION,
            "source_dir": str(config.source_dir),
            "targets": [
                {"name": target.name, "path": str(target.path)}
                for target in config.targets
            ],
        },
    )


def _validate_config(config: SkillLinkConfig) -> None:
    if not config.targets:
        raise ValueError("at least one target is required")

    seen_names: set[str] = set()
    for target in config.targets:
        if not _is_valid_target_name(target.name):
            raise ValueError(f"invalid target name: {target.name}")
        if target.name in seen_names:
            raise ValueError(f"duplicate target name: {target.name}")
        seen_names.add(target.name)


def _is_valid_target_name(name: object) -> bool:
    return isinstance(name, str) and bool(TARGET_NAME_PATTERN.fullmatch(name))
