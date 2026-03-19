from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def make_layout(paths_module, tmp_path: Path):
    return paths_module.AgentKitLayout(
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
    )


def make_store(registry_module, layout: Path, plugins: dict[str, object]):
    return registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: {"schema_version": 1, "plugins": plugins},
        registry_fetcher=lambda url: "{}",
    )


def wheel_plugin_data(
    *,
    version: str = "0.2.0",
    wheel_url: str = "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl",
    sha256: str = "abc123",
) -> dict[str, object]:
    return {
        "plugin_id": "skills-link",
        "display_name": "Skills Link",
        "description": "wheel plugin",
        "source_type": "wheel",
        "package_name": "skills-link",
        "version": version,
        "wheel_url": wheel_url,
        "sha256": sha256,
        "api_version": 1,
        "min_core_version": "0.1.0",
    }


def test_jsonc_loader_accepts_comments_and_keeps_urls(tmp_path: Path):
    jsonc = require_module("agent_kit.jsonc")
    path = tmp_path / "config.jsonc"
    path.write_text(
        '{\n'
        '  // comment\n'
        '  "url": "https://example.com/path",\n'
        '  "value": 1\n'
        '}\n',
        encoding="utf-8",
    )

    data = jsonc.load_jsonc(path)

    assert data == {"url": "https://example.com/path", "value": 1}


def test_registry_refresh_updates_cache_and_cached_entries_override_builtin(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    layout = make_layout(paths_module, tmp_path)
    builtin_registry = {
        "schema_version": 1,
        "plugins": {
            "skills-link": {
                "plugin_id": "skills-link",
                "display_name": "Skills Link",
                "description": "builtin",
                "source_type": "git",
                "git_url": "https://example.com/repo.git",
                "subdirectory": "packages/skills-link",
                "version": "0.1.0",
                "tag": "v0.1.0",
                "commit": "old",
                "api_version": 1,
                "min_core_version": "0.1.0",
            }
        },
    }
    remote_registry = {
        "schema_version": 1,
        "plugins": {
            "skills-link": {
                "plugin_id": "skills-link",
                "display_name": "Skills Link",
                "description": "remote",
                "source_type": "git",
                "git_url": "https://example.com/repo.git",
                "subdirectory": "packages/skills-link",
                "version": "0.2.0",
                "tag": "v0.2.0",
                "commit": "new",
                "api_version": 1,
                "min_core_version": "0.1.0",
            }
        },
    }

    store = registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: builtin_registry,
        registry_fetcher=lambda url: json.dumps(remote_registry),
    )

    refreshed = store.refresh()
    effective = store.load_effective_registry()

    assert refreshed["skills-link"].version == "0.2.0"
    assert effective["skills-link"].description == "remote"
    assert layout.registry_cache_path.exists()


def test_registry_plugin_supports_wheel_source():
    registry_module = require_module("agent_kit.registry")

    entry = registry_module.RegistryPlugin.from_dict(
        {
            "plugin_id": "skills-link",
            "display_name": "Skills Link",
            "description": "wheel plugin",
            "source_type": "wheel",
            "package_name": "skills-link",
            "version": "0.2.0",
            "wheel_url": "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl",
            "sha256": "abc123",
            "api_version": 1,
            "min_core_version": "0.1.0",
        }
    )

    assert entry.wheel_url == "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl"
    assert entry.sha256 == "abc123"
    assert entry.install_spec() == "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl"


def test_builtin_registry_includes_opencode_env_switch():
    registry_module = require_module("agent_kit.registry")

    registry = registry_module.load_builtin_registry()

    assert "opencode-env-switch" in registry["plugins"]
    assert registry["plugins"]["opencode-env-switch"]["package_name"] == "opencode-env-switch"


def test_layout_supports_plugin_artifact_paths(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    layout = make_layout(paths_module, tmp_path)

    artifact_dir = layout.plugin_artifact_dir("skills-link")
    artifact_path = layout.plugin_artifact_path(
        "skills-link",
        "skills_link-0.2.0-py3-none-any.whl",
    )

    assert artifact_dir == layout.cache_root / "artifacts" / "skills-link"
    assert artifact_path == artifact_dir / "skills_link-0.2.0-py3-none-any.whl"


def test_install_rejects_plugin_ids_not_in_registry(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: {"schema_version": 1, "plugins": {}},
        registry_fetcher=lambda url: "{}",
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)

    with pytest.raises(manager_module.PluginError, match="Unknown official plugin"):
        manager.install_plugin("skills-link")


def test_install_rolls_back_when_plugin_metadata_mismatches(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: {
            "schema_version": 1,
            "plugins": {
                "skills-link": {
                    "plugin_id": "skills-link",
                    "display_name": "Skills Link",
                    "description": "plugin",
                    "source_type": "pypi",
                    "package_name": "skills-link",
                    "version": "0.1.0",
                    "api_version": 1,
                    "min_core_version": "0.1.0",
                }
            },
        },
        registry_fetcher=lambda url: "{}",
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)

    manager.command_runner = lambda *args, **kwargs: None
    manager.probe_plugin_metadata = lambda plugin_id: {
        "plugin_id": "wrong-plugin",
        "installed_version": "0.1.0",
        "api_version": 1,
        "config_version": 1,
    }
    manager.probe_distribution_metadata = lambda entry: {
        "package_name": "skills-link",
        "version": "0.1.0",
        "direct_url": None,
    }

    with pytest.raises(manager_module.PluginError, match="plugin metadata mismatch"):
        manager.install_plugin("skills-link")

    assert not layout.plugin_data_dir("skills-link").exists()


def test_install_supports_git_source_and_records_latest_version(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: {
            "schema_version": 1,
            "plugins": {
                "skills-link": {
                    "plugin_id": "skills-link",
                    "display_name": "Skills Link",
                    "description": "plugin",
                    "source_type": "git",
                    "git_url": "https://example.com/repo.git",
                    "subdirectory": "packages/skills-link",
                    "version": "0.2.0",
                    "tag": "v0.2.0",
                    "commit": "abc123",
                    "package_name": "skills-link",
                    "api_version": 1,
                    "min_core_version": "0.1.0",
                }
            },
        },
        registry_fetcher=lambda url: "{}",
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)

    manager.command_runner = lambda *args, **kwargs: None
    manager.probe_plugin_metadata = lambda plugin_id: {
        "plugin_id": "skills-link",
        "installed_version": "0.2.0",
        "api_version": 1,
        "config_version": 1,
    }
    manager.probe_distribution_metadata = lambda entry: {
        "package_name": "skills-link",
        "version": "0.2.0",
        "direct_url": {"url": "https://example.com/repo.git", "vcs_info": {"vcs": "git", "commit_id": "abc123"}},
    }

    record = manager.install_plugin("skills-link")

    assert record.installed_version == "0.2.0"
    assert record.latest_known_version == "0.2.0"
    assert record.source_type == "git"
    assert record.source_ref.endswith("@abc123#subdirectory=packages/skills-link")


def test_install_supports_wheel_source_and_records_sha256(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = make_store(
        registry_module,
        layout,
        {"skills-link": wheel_plugin_data()},
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)
    commands: list[list[str]] = []
    downloaded_paths: list[Path] = []

    def command_runner(args, **kwargs):
        commands.append(list(args))
        return None

    def download_artifact(url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("wheel-bytes", encoding="utf-8")
        downloaded_paths.append(destination)
        return destination

    manager.command_runner = command_runner
    manager.download_artifact = download_artifact
    manager.hash_artifact = lambda path: "abc123"
    manager.probe_plugin_metadata = lambda plugin_id: {
        "plugin_id": "skills-link",
        "installed_version": "0.2.0",
        "api_version": 1,
        "config_version": 1,
    }
    manager.probe_distribution_metadata = lambda entry: {
        "package_name": "skills-link",
        "version": "0.2.0",
        "direct_url": None,
    }

    record = manager.install_plugin("skills-link")

    expected_artifact = layout.plugin_artifact_path(
        "skills-link", "skills_link-0.2.0-py3-none-any.whl"
    )
    assert downloaded_paths == [expected_artifact]
    assert any(command[:4] == ["uv", "pip", "install", "--python"] for command in commands)
    assert any(command[-1] == str(expected_artifact) for command in commands)
    assert record.source_type == "wheel"
    assert record.source_ref == "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl"
    assert record.source_sha256 == "abc123"


def test_install_reuses_cached_wheel_when_hash_matches(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = make_store(
        registry_module,
        layout,
        {"skills-link": wheel_plugin_data()},
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)
    cached_artifact = layout.cache_root / "artifacts" / "skills-link" / "skills_link-0.2.0-py3-none-any.whl"
    cached_artifact.parent.mkdir(parents=True, exist_ok=True)
    cached_artifact.write_text("wheel-bytes", encoding="utf-8")
    download_calls: list[tuple[str, Path]] = []

    manager.command_runner = lambda *args, **kwargs: None
    manager.download_artifact = lambda url, destination: download_calls.append((url, destination))
    manager.hash_artifact = lambda path: "abc123"
    manager.probe_plugin_metadata = lambda plugin_id: {
        "plugin_id": "skills-link",
        "installed_version": "0.2.0",
        "api_version": 1,
        "config_version": 1,
    }
    manager.probe_distribution_metadata = lambda entry: {
        "package_name": "skills-link",
        "version": "0.2.0",
        "direct_url": None,
    }

    record = manager.install_plugin("skills-link")

    assert download_calls == []
    assert record.source_sha256 == "abc123"


def test_install_stops_when_wheel_hash_mismatches(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = make_store(
        registry_module,
        layout,
        {"skills-link": wheel_plugin_data()},
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)
    commands: list[list[str]] = []

    def command_runner(args, **kwargs):
        commands.append(list(args))
        return None

    def download_artifact(url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("wheel-bytes", encoding="utf-8")
        return destination

    manager.command_runner = command_runner
    manager.download_artifact = download_artifact
    manager.hash_artifact = lambda path: "wrong"

    with pytest.raises(manager_module.PluginError, match="artifact hash mismatch"):
        manager.install_plugin("skills-link")

    assert not any(command[:4] == ["uv", "pip", "install", "--python"] for command in commands)


def test_update_plugin_uses_latest_wheel_entry(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    registry_doc = {"schema_version": 1, "plugins": {"skills-link": wheel_plugin_data()}}
    store = registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: registry_doc,
        registry_fetcher=lambda url: "{}",
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)
    manager.command_runner = lambda *args, **kwargs: None
    def download_artifact(url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("wheel-bytes", encoding="utf-8")
        return destination

    manager.download_artifact = download_artifact
    manager.hash_artifact = lambda path: (
        "def456" if path.name == "skills_link-0.3.0-py3-none-any.whl" else "abc123"
    )
    manager.probe_plugin_metadata = lambda plugin_id: {
        "plugin_id": "skills-link",
        "installed_version": (
            "0.3.0"
            if registry_doc["plugins"]["skills-link"]["version"] == "0.3.0"
            else "0.2.0"
        ),
        "api_version": 1,
        "config_version": 1,
    }
    manager.probe_distribution_metadata = lambda entry: {
        "package_name": "skills-link",
        "version": entry.version,
        "direct_url": None,
    }

    manager.install_plugin("skills-link")
    registry_doc["plugins"]["skills-link"] = wheel_plugin_data(
        version="0.3.0",
        wheel_url="https://example.com/releases/skills_link-0.3.0-py3-none-any.whl",
        sha256="def456",
    )

    record = manager.update_plugin("skills-link")

    assert record.installed_version == "0.3.0"
    assert record.latest_known_version == "0.3.0"
    assert record.source_ref == "https://example.com/releases/skills_link-0.3.0-py3-none-any.whl"
    assert record.source_sha256 == "def456"


def test_remove_plugin_keeps_config_by_default_and_can_purge(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: {"schema_version": 1, "plugins": {}},
        registry_fetcher=lambda url: "{}",
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)

    layout.plugin_config_dir("skills-link").mkdir(parents=True, exist_ok=True)
    layout.plugin_data_dir("skills-link").mkdir(parents=True, exist_ok=True)
    layout.plugin_state_path("skills-link").write_text("{}", encoding="utf-8")

    manager.remove_plugin("skills-link")
    assert layout.plugin_config_dir("skills-link").exists()
    assert not layout.plugin_data_dir("skills-link").exists()

    layout.plugin_data_dir("skills-link").mkdir(parents=True, exist_ok=True)
    layout.plugin_state_path("skills-link").write_text("{}", encoding="utf-8")
    manager.remove_plugin("skills-link", purge_config=True)
    assert not layout.plugin_config_dir("skills-link").exists()


def test_load_record_keeps_backward_compatibility_without_source_sha256(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    layout = make_layout(paths_module, tmp_path)
    store = make_store(registry_module, layout, {})
    manager = manager_module.PluginManager(layout=layout, registry_store=store)
    layout.plugin_data_dir("skills-link").mkdir(parents=True, exist_ok=True)
    layout.plugin_state_path("skills-link").write_text(
        json.dumps(
            {
                "plugin_id": "skills-link",
                "installed_version": "0.1.0",
                "latest_known_version": "0.1.0",
                "source_type": "git",
                "source_ref": "git+https://example.com/repo.git@abc123",
                "api_version": 1,
                "config_version": 1,
                "venv_path": str(layout.plugin_venv_dir("skills-link")),
                "executable_path": str(layout.plugin_executable_path("skills-link")),
                "installed_at": "2026-03-18T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    record = manager._load_record("skills-link")

    assert record is not None
    assert record.source_sha256 is None


def test_run_plugin_blocks_on_config_version_mismatch(tmp_path: Path):
    paths_module = require_module("agent_kit.paths")
    registry_module = require_module("agent_kit.registry")
    manager_module = require_module("agent_kit.plugin_manager")
    jsonc_module = require_module("agent_kit.jsonc")
    layout = make_layout(paths_module, tmp_path)
    store = registry_module.RegistryStore(
        layout=layout,
        builtin_registry_loader=lambda: {"schema_version": 1, "plugins": {}},
        registry_fetcher=lambda url: "{}",
    )
    manager = manager_module.PluginManager(layout=layout, registry_store=store)
    layout.plugin_data_dir("skills-link").mkdir(parents=True, exist_ok=True)
    layout.plugin_config_dir("skills-link").mkdir(parents=True, exist_ok=True)
    jsonc_module.write_jsonc(
        layout.plugin_config_path("skills-link"),
        {"config_version": 2, "source_dir": "/tmp/source", "target_dir": "/tmp/target"},
    )
    layout.plugin_state_path("skills-link").write_text(
        json.dumps(
            {
                "plugin_id": "skills-link",
                "installed_version": "0.1.0",
                "latest_known_version": "0.1.0",
                "source_type": "git",
                "source_ref": "ref",
                "api_version": 1,
                "config_version": 1,
                "venv_path": str(layout.plugin_venv_dir("skills-link")),
                "executable_path": str(layout.plugin_executable_path("skills-link")),
                "installed_at": "2026-03-17T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    manager.probe_plugin_metadata = lambda plugin_id: {
        "plugin_id": "skills-link",
        "installed_version": "0.1.0",
        "api_version": 1,
        "config_version": 1,
    }

    with pytest.raises(manager_module.PluginError, match="config version mismatch"):
        manager.run_plugin("skills-link", ["status"])
