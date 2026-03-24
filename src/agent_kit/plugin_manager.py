from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from packaging.version import Version

from agent_kit import __version__ as CORE_VERSION
from agent_kit.jsonc import load_jsonc
from agent_kit.locale import resolve_language
from agent_kit.paths import AgentKitLayout
from agent_kit.registry import RegistryPlugin, RegistryStore


class PluginError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class InstalledPluginRecord:
    plugin_id: str
    installed_version: str
    latest_known_version: str
    source_type: str
    source_ref: str
    source_sha256: str | None
    api_version: int
    config_version: int
    venv_path: str
    executable_path: str
    installed_at: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "InstalledPluginRecord":
        return cls(
            plugin_id=str(data["plugin_id"]),
            installed_version=str(data["installed_version"]),
            latest_known_version=str(data["latest_known_version"]),
            source_type=str(data["source_type"]),
            source_ref=str(data["source_ref"]),
            source_sha256=_optional_str(data.get("source_sha256")),
            api_version=int(data["api_version"]),
            config_version=int(data["config_version"]),
            venv_path=str(data["venv_path"]),
            executable_path=str(data["executable_path"]),
            installed_at=str(data["installed_at"]),
        )


@dataclass(slots=True, frozen=True)
class RunnablePlugin:
    plugin_id: str
    description: str


@dataclass(slots=True, frozen=True)
class BrokenPlugin:
    plugin_id: str
    status: str
    reason: str


@dataclass(slots=True, frozen=True)
class PluginInfo:
    plugin_id: str
    description: str
    source_type: str
    status: str
    available_version: str | None
    installed_version: str | None
    tag: str | None
    commit: str | None
    config_path: Path
    venv_path: Path


class PluginManager:
    def __init__(
        self,
        *,
        layout: AgentKitLayout,
        registry_store: RegistryStore,
        command_runner: Callable[..., subprocess.CompletedProcess[str] | None] | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.layout = layout
        self.registry_store = registry_store
        self.command_runner = command_runner or self._run_command
        self.now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self.download_artifact = self._download_artifact
        self.hash_artifact = self._hash_artifact

    @classmethod
    def from_defaults(cls) -> "PluginManager":
        layout = AgentKitLayout.from_environment()
        store = RegistryStore(layout=layout)
        return cls(layout=layout, registry_store=store)

    def refresh_registry(self) -> dict[str, RegistryPlugin]:
        return self.registry_store.refresh()

    def install_plugin(self, plugin_id: str) -> InstalledPluginRecord:
        registry = self.registry_store.load_effective_registry()
        entry = registry.get(plugin_id)
        if entry is None:
            raise PluginError(f"Unknown official plugin: {plugin_id}")
        self._ensure_core_compatible(entry)

        data_dir = self.layout.plugin_data_dir(plugin_id)
        if data_dir.exists():
            shutil.rmtree(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._create_plugin_environment(plugin_id)
            install_target = self._resolve_install_target(entry)
            self._install_distribution(plugin_id, install_target)
            runtime_metadata = self.probe_plugin_metadata(plugin_id)
            distribution_metadata = self.probe_distribution_metadata(entry)
            self._verify_installation(entry, runtime_metadata, distribution_metadata)
            record = InstalledPluginRecord(
                plugin_id=plugin_id,
                installed_version=str(runtime_metadata["installed_version"]),
                latest_known_version=entry.version,
                source_type=entry.source_type,
                source_ref=self._source_ref(entry),
                source_sha256=entry.sha256 if entry.source_type == "wheel" else None,
                api_version=int(runtime_metadata["api_version"]),
                config_version=int(runtime_metadata["config_version"]),
                venv_path=str(self.layout.plugin_venv_dir(plugin_id)),
                executable_path=str(self.layout.plugin_executable_path(plugin_id)),
                installed_at=self.now_factory().isoformat(),
            )
            self._write_record(record)
            return record
        except Exception as exc:
            if data_dir.exists():
                shutil.rmtree(data_dir)
            if isinstance(exc, PluginError):
                raise
            raise PluginError(str(exc)) from exc

    def update_plugin(self, plugin_id: str) -> InstalledPluginRecord:
        return self.install_plugin(plugin_id)

    def remove_plugin(self, plugin_id: str, *, purge_config: bool = False) -> None:
        data_dir = self.layout.plugin_data_dir(plugin_id)
        if data_dir.exists():
            shutil.rmtree(data_dir)
        if purge_config:
            config_dir = self.layout.plugin_config_dir(plugin_id)
            if config_dir.exists():
                shutil.rmtree(config_dir)

    def run_plugin(self, plugin_id: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        record = self._load_record(plugin_id)
        if record is None:
            raise PluginError(f"plugin is not installed: {plugin_id}")

        metadata = self.probe_plugin_metadata(plugin_id)
        if metadata.get("plugin_id") != plugin_id:
            raise PluginError(f"plugin metadata mismatch for {plugin_id}")
        if int(metadata.get("api_version", -1)) != record.api_version:
            raise PluginError(f"plugin api version mismatch for {plugin_id}")
        if self.layout.plugin_config_path(plugin_id).exists():
            config_data = load_jsonc(self.layout.plugin_config_path(plugin_id))
            config_version = int(config_data.get("config_version", 0))
            if config_version != int(metadata["config_version"]):
                raise PluginError(
                    f"config version mismatch for {plugin_id}: "
                    f"{config_version} != {metadata['config_version']}"
                )

        executable = Path(record.executable_path)
        if not executable.exists():
            raise PluginError(f"plugin executable is missing: {executable}")

        return self.command_runner(
            [str(executable), *args],
            env=self._plugin_environment(plugin_id),
            capture_output=True,
            text=True,
        )

    def get_plugin_info(self, plugin_id: str) -> PluginInfo:
        registry = self.registry_store.load_effective_registry()
        entry = registry.get(plugin_id)
        record = self._load_record(plugin_id)
        description = entry.description if entry else "unknown plugin"
        return PluginInfo(
            plugin_id=plugin_id,
            description=description,
            source_type=entry.source_type if entry else (record.source_type if record else "unknown"),
            status="installed" if record else "available" if entry else "unknown",
            available_version=entry.version if entry else None,
            installed_version=record.installed_version if record else None,
            tag=entry.tag if entry else None,
            commit=entry.commit if entry else None,
            config_path=self.layout.plugin_config_path(plugin_id),
            venv_path=self.layout.plugin_venv_dir(plugin_id),
        )

    def list_plugins(self) -> list[PluginInfo]:
        registry = self.registry_store.load_effective_registry()
        plugin_ids = sorted(
            set(registry.keys()) | {path.name for path in (self.layout.data_root / "plugins").glob("*") if path.is_dir()}
        )
        return [self.get_plugin_info(plugin_id) for plugin_id in plugin_ids]

    def runnable_plugins(self) -> list[RunnablePlugin]:
        registry = self.registry_store.load_effective_registry()
        runnable: list[RunnablePlugin] = []
        for record in self._installed_records():
            executable = Path(record.executable_path)
            if executable.exists():
                description = registry.get(record.plugin_id).description if record.plugin_id in registry else "installed plugin"
                runnable.append(
                    RunnablePlugin(plugin_id=record.plugin_id, description=description)
                )
        return sorted(runnable, key=lambda item: item.plugin_id)

    def broken_plugins(self) -> list[BrokenPlugin]:
        broken: list[BrokenPlugin] = []
        for record in self._installed_records():
            executable = Path(record.executable_path)
            if not executable.exists():
                broken.append(
                    BrokenPlugin(
                        plugin_id=record.plugin_id,
                        status="broken",
                        reason="missing executable",
                    )
                )
        return sorted(broken, key=lambda item: item.plugin_id)

    def probe_plugin_metadata(self, plugin_id: str) -> dict[str, object]:
        executable = self.layout.plugin_executable_path(plugin_id)
        if not executable.exists():
            raise PluginError(f"plugin executable is missing: {executable}")
        result = self.command_runner(
            [str(executable), "--plugin-metadata"],
            env=self._plugin_environment(plugin_id),
            capture_output=True,
            text=True,
        )
        self._ensure_command_success(result)
        return json.loads(result.stdout)

    def probe_distribution_metadata(self, entry: RegistryPlugin) -> dict[str, object]:
        package_name = entry.package_name
        if not package_name:
            raise PluginError(f"missing package name for {entry.plugin_id}")
        python_path = self.layout.plugin_python_path(entry.plugin_id)
        script = (
            "import importlib.metadata, json\n"
            f"dist = importlib.metadata.distribution({package_name!r})\n"
            "direct_url = dist.read_text('direct_url.json')\n"
            "print(json.dumps({"
            f"'package_name': {package_name!r}, "
            "'version': dist.version, "
            "'direct_url': json.loads(direct_url) if direct_url else None"
            "}))\n"
        )
        result = self.command_runner(
            [str(python_path), "-c", script],
            capture_output=True,
            text=True,
        )
        self._ensure_command_success(result)
        return json.loads(result.stdout)

    def _create_plugin_environment(self, plugin_id: str) -> None:
        self.command_runner(
            ["uv", "venv", str(self.layout.plugin_venv_dir(plugin_id))],
            capture_output=True,
            text=True,
        )

    def _install_distribution(self, plugin_id: str, install_target: str) -> None:
        self.command_runner(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(self.layout.plugin_python_path(plugin_id)),
                install_target,
            ],
            capture_output=True,
            text=True,
        )

    def _resolve_install_target(self, entry: RegistryPlugin) -> str:
        if entry.source_type != "wheel":
            return entry.install_spec()
        artifact_path = self._prepare_wheel_artifact(entry)
        return str(artifact_path)

    def _prepare_wheel_artifact(self, entry: RegistryPlugin) -> Path:
        if not entry.wheel_url or not entry.sha256:
            raise PluginError(f"missing wheel source for {entry.plugin_id}")

        artifact_name = self._artifact_filename(entry.wheel_url)
        artifact_path = self.layout.plugin_artifact_path(entry.plugin_id, artifact_name)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        if artifact_path.exists():
            cached_hash = self.hash_artifact(artifact_path)
            if cached_hash == entry.sha256:
                return artifact_path

        downloaded_path = self.download_artifact(entry.wheel_url, artifact_path)
        actual_hash = self.hash_artifact(downloaded_path)
        if actual_hash != entry.sha256:
            downloaded_path.unlink(missing_ok=True)
            raise PluginError(f"artifact hash mismatch for {entry.plugin_id}")
        return downloaded_path

    def _source_ref(self, entry: RegistryPlugin) -> str:
        if entry.source_type == "wheel" and entry.wheel_url:
            return entry.wheel_url
        return entry.install_spec()

    def _verify_installation(
        self,
        entry: RegistryPlugin,
        runtime_metadata: dict[str, object],
        distribution_metadata: dict[str, object],
    ) -> None:
        if runtime_metadata.get("plugin_id") != entry.plugin_id:
            raise PluginError(f"plugin metadata mismatch for {entry.plugin_id}")
        if int(runtime_metadata.get("api_version", -1)) != entry.api_version:
            raise PluginError(f"plugin metadata mismatch for {entry.plugin_id}")
        if entry.package_name and distribution_metadata.get("package_name") != entry.package_name:
            raise PluginError(f"distribution metadata mismatch for {entry.plugin_id}")
        if str(distribution_metadata.get("version")) != entry.version:
            raise PluginError(f"distribution metadata mismatch for {entry.plugin_id}")
        if entry.source_type == "git":
            direct_url = distribution_metadata.get("direct_url") or {}
            url = direct_url.get("url")
            if url != entry.git_url:
                raise PluginError(f"distribution metadata mismatch for {entry.plugin_id}")

    def _write_record(self, record: InstalledPluginRecord) -> None:
        path = self.layout.plugin_state_path(record.plugin_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(record), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _load_record(self, plugin_id: str) -> InstalledPluginRecord | None:
        path = self.layout.plugin_state_path(plugin_id)
        if not path.exists():
            return None
        return InstalledPluginRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _installed_records(self) -> list[InstalledPluginRecord]:
        plugins_dir = self.layout.data_root / "plugins"
        if not plugins_dir.exists():
            return []
        records: list[InstalledPluginRecord] = []
        for entry in sorted(plugins_dir.iterdir()):
            state_path = entry / "plugin.json"
            if state_path.exists():
                records.append(
                    InstalledPluginRecord.from_dict(
                        json.loads(state_path.read_text(encoding="utf-8"))
                    )
                )
        return records

    def _plugin_environment(self, plugin_id: str) -> dict[str, str]:
        env = dict(os.environ)
        env["AGENT_KIT_CONFIG_DIR"] = str(self.layout.config_root)
        env["AGENT_KIT_DATA_DIR"] = str(self.layout.data_root)
        env["AGENT_KIT_CACHE_DIR"] = str(self.layout.cache_root)
        env["AGENT_KIT_PLUGIN_ID"] = plugin_id
        env["AGENT_KIT_LANG"] = resolve_language(config_path=self.layout.global_config_path).code
        return env

    def _ensure_core_compatible(self, entry: RegistryPlugin) -> None:
        if Version(CORE_VERSION) < Version(entry.min_core_version):
            raise PluginError(
                f"plugin {entry.plugin_id} requires agent-kit>={entry.min_core_version}"
            )

    def _download_artifact(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url) as response:
            destination.write_bytes(response.read())
        return destination

    def _hash_artifact(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _artifact_filename(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        filename = Path(parsed.path).name
        if not filename or not filename.endswith(".whl"):
            raise PluginError(f"invalid wheel artifact url: {url}")
        return filename

    def _run_command(self, *args, **kwargs) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(*args, **kwargs, check=False)
        self._ensure_command_success(result)
        return result

    def _ensure_command_success(self, result: subprocess.CompletedProcess[str] | None) -> None:
        if result is None:
            return
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "unknown command failure"
            raise PluginError(stderr)


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
