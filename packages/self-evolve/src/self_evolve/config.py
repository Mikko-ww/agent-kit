from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from self_evolve import CONFIG_VERSION, PLUGIN_ID
from self_evolve.jsonc import load_jsonc, write_jsonc

AGENT_DIR_NAME = ".agent"
MEMORIES_DIR_NAME = "memories"
SKILLS_DIR_NAME = "skills"


@dataclass(slots=True, frozen=True)
class ProjectConfig:
    project_root: Path

    @property
    def agent_dir(self) -> Path:
        return self.project_root / AGENT_DIR_NAME

    @property
    def memories_dir(self) -> Path:
        return self.agent_dir / MEMORIES_DIR_NAME

    @property
    def skills_dir(self) -> Path:
        return self.agent_dir / SKILLS_DIR_NAME

    @property
    def config_file(self) -> Path:
        return self.agent_dir / "config.jsonc"


def plugin_config_path(config_root: Path) -> Path:
    return config_root / "plugins" / PLUGIN_ID / "config.jsonc"


def load_plugin_config(config_root: Path) -> dict | None:
    path = plugin_config_path(config_root)
    if not path.exists():
        return None
    data = load_jsonc(path)
    if not isinstance(data, dict):
        return None
    if data.get("config_version") != CONFIG_VERSION:
        return None
    return data


def save_plugin_config(config_root: Path, project_root: Path) -> Path:
    return write_jsonc(
        plugin_config_path(config_root),
        {
            "plugin_id": PLUGIN_ID,
            "config_version": CONFIG_VERSION,
            "project_root": str(project_root),
        },
    )


def load_project_config(project_root: Path) -> ProjectConfig | None:
    agent_dir = project_root / AGENT_DIR_NAME
    if not agent_dir.exists() or not agent_dir.is_dir():
        return None
    return ProjectConfig(project_root=project_root)


def save_project_config(config: ProjectConfig) -> Path:
    return write_jsonc(
        config.config_file,
        {
            "plugin_id": PLUGIN_ID,
            "config_version": CONFIG_VERSION,
        },
    )
