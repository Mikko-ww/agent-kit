from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from importlib import resources
from typing import Callable

from agent_kit.jsonc import load_jsonc
from agent_kit.paths import AgentKitLayout

OFFICIAL_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Mikko-ww/agent-kit/main/registry/official.json"
)


@dataclass(slots=True, frozen=True)
class RegistryPlugin:
    plugin_id: str
    display_name: str
    description: str
    source_type: str
    version: str
    api_version: int
    min_core_version: str
    package_name: str | None = None
    git_url: str | None = None
    subdirectory: str | None = None
    tag: str | None = None
    commit: str | None = None
    wheel_url: str | None = None
    sha256: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RegistryPlugin":
        return cls(
            plugin_id=str(data["plugin_id"]),
            display_name=str(data["display_name"]),
            description=str(data["description"]),
            source_type=str(data["source_type"]),
            version=str(data["version"]),
            api_version=int(data["api_version"]),
            min_core_version=str(data["min_core_version"]),
            package_name=_optional_str(data.get("package_name")),
            git_url=_optional_str(data.get("git_url")),
            subdirectory=_optional_str(data.get("subdirectory")),
            tag=_optional_str(data.get("tag")),
            commit=_optional_str(data.get("commit")),
            wheel_url=_optional_str(data.get("wheel_url")),
            sha256=_optional_str(data.get("sha256")),
        )

    def install_spec(self) -> str:
        if self.source_type == "pypi":
            if not self.package_name:
                raise ValueError(f"missing package name for {self.plugin_id}")
            return f"{self.package_name}=={self.version}"

        if self.source_type == "git":
            if not self.git_url or not self.commit:
                raise ValueError(f"missing git source for {self.plugin_id}")
            spec = f"git+{self.git_url}@{self.commit}"
            if self.subdirectory:
                spec = f"{spec}#subdirectory={self.subdirectory}"
            return spec

        if self.source_type == "wheel":
            if not self.wheel_url or not self.sha256 or not self.package_name:
                raise ValueError(f"missing wheel source for {self.plugin_id}")
            return self.wheel_url

        raise ValueError(f"unsupported source type: {self.source_type}")


class RegistryStore:
    def __init__(
        self,
        *,
        layout: AgentKitLayout,
        builtin_registry_loader: Callable[[], dict[str, object]] | None = None,
        registry_fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self.layout = layout
        self.builtin_registry_loader = builtin_registry_loader or load_builtin_registry
        self.registry_fetcher = registry_fetcher or fetch_registry

    def load_effective_registry(self) -> dict[str, RegistryPlugin]:
        builtin_doc = self.builtin_registry_loader()
        cache_doc = self._load_cached_registry()
        return self._merge_registry_docs(builtin_doc, cache_doc)

    def refresh(self) -> dict[str, RegistryPlugin]:
        payload = self.registry_fetcher(OFFICIAL_REGISTRY_URL)
        self.layout.registry_cache_path.parent.mkdir(parents=True, exist_ok=True)
        parsed = json.loads(payload)
        self.layout.registry_cache_path.write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self.load_effective_registry()

    def _load_cached_registry(self) -> dict[str, object]:
        if not self.layout.registry_cache_path.exists():
            return {"schema_version": 1, "plugins": {}}
        return json.loads(self.layout.registry_cache_path.read_text(encoding="utf-8"))

    def _merge_registry_docs(
        self,
        builtin_doc: dict[str, object],
        cache_doc: dict[str, object],
    ) -> dict[str, RegistryPlugin]:
        merged_plugins = {
            **dict(builtin_doc.get("plugins", {})),
            **dict(cache_doc.get("plugins", {})),
        }
        return {
            plugin_id: RegistryPlugin.from_dict(plugin_data)
            for plugin_id, plugin_data in merged_plugins.items()
        }


def load_builtin_registry() -> dict[str, object]:
    content = resources.files("agent_kit").joinpath("official_registry.json").read_text(
        encoding="utf-8"
    )
    return json.loads(content)


def fetch_registry(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
