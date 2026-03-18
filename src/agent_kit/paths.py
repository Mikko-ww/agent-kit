from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _expand_path(value: str) -> Path:
    return Path(value).expanduser()


@dataclass(slots=True, frozen=True)
class AgentKitLayout:
    config_root: Path
    data_root: Path
    cache_root: Path

    @classmethod
    def from_environment(cls) -> "AgentKitLayout":
        config_root = _expand_path(
            os.environ.get("AGENT_KIT_CONFIG_DIR", "~/.config/agent-kit")
        )
        data_root = _expand_path(
            os.environ.get("AGENT_KIT_DATA_DIR", "~/.local/share/agent-kit")
        )
        cache_root = _expand_path(
            os.environ.get("AGENT_KIT_CACHE_DIR", "~/.cache/agent-kit")
        )
        return cls(
            config_root=config_root,
            data_root=data_root,
            cache_root=cache_root,
        )

    @property
    def global_config_path(self) -> Path:
        return self.config_root / "config.jsonc"

    @property
    def registry_cache_path(self) -> Path:
        return self.cache_root / "registry.json"

    def plugin_artifact_dir(self, plugin_id: str) -> Path:
        return self.cache_root / "artifacts" / plugin_id

    def plugin_artifact_path(self, plugin_id: str, filename: str) -> Path:
        return self.plugin_artifact_dir(plugin_id) / filename

    def plugin_config_dir(self, plugin_id: str) -> Path:
        return self.config_root / "plugins" / plugin_id

    def plugin_config_path(self, plugin_id: str) -> Path:
        return self.plugin_config_dir(plugin_id) / "config.jsonc"

    def plugin_data_dir(self, plugin_id: str) -> Path:
        return self.data_root / "plugins" / plugin_id

    def plugin_state_path(self, plugin_id: str) -> Path:
        return self.plugin_data_dir(plugin_id) / "plugin.json"

    def plugin_venv_dir(self, plugin_id: str) -> Path:
        return self.plugin_data_dir(plugin_id) / "venv"

    def plugin_executable_path(self, plugin_id: str) -> Path:
        return self.plugin_venv_dir(plugin_id) / "bin" / "agent-kit-plugin"

    def plugin_python_path(self, plugin_id: str) -> Path:
        return self.plugin_venv_dir(plugin_id) / "bin" / "python"
