from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def test_help_lists_installed_plugins_only(tmp_path: Path):
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills")
        ],
        broken_plugins=lambda: [
            SimpleNamespace(plugin_id="broken", status="broken", reason="missing executable")
        ],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "plugins" in result.output
    assert "skills-link" in result.output
    assert "broken" in result.output
    assert "missing executable" in result.output


def test_dynamic_plugin_command_forwards_extra_args():
    cli = require_module("agent_kit.cli")
    calls: list[tuple[str, list[str]]] = []
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills")
        ],
        broken_plugins=lambda: [],
        run_plugin=lambda plugin_id, args: calls.append((plugin_id, args)) or SimpleNamespace(
            returncode=0,
            stdout="ok\n",
            stderr="",
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["skills-link", "status", "--verbose"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert calls == [("skills-link", ["status", "--verbose"])]


def test_plugins_refresh_command_uses_manager():
    cli = require_module("agent_kit.cli")
    called = {}

    def refresh_registry():
        called["refresh"] = True
        return {
            "skills-link": SimpleNamespace(plugin_id="skills-link", version="0.2.0")
        }

    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
        refresh_registry=refresh_registry,
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["plugins", "refresh"])

    assert result.exit_code == 0
    assert called["refresh"] is True
    assert "skills-link" in result.output


def test_plugins_info_shows_installed_and_available_versions():
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
        get_plugin_info=lambda plugin_id: SimpleNamespace(
            plugin_id=plugin_id,
            description="Link local skills",
            source_type="git",
            available_version="0.2.0",
            installed_version="0.1.0",
            tag="v0.2.0",
            commit="abc123",
            status="installed",
            config_path=Path("/tmp/config.jsonc"),
            venv_path=Path("/tmp/venv"),
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["plugins", "info", "skills-link"])

    assert result.exit_code == 0
    assert "available_version: 0.2.0" in result.output
    assert "installed_version: 0.1.0" in result.output
    assert "config_path: /tmp/config.jsonc" in result.output


def test_help_uses_zh_cn_when_config_requests_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    config_root = tmp_path / "config"
    config_root.mkdir(parents=True)
    (config_root / "config.jsonc").write_text(
        json.dumps({"language": "zh-CN"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_KIT_CONFIG_DIR", str(config_root))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "官方插件管理与执行 CLI。" in result.output
    assert "管理官方插件。" in result.output


def test_config_set_and_get_language(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    config_root = tmp_path / "config"
    monkeypatch.setenv("AGENT_KIT_CONFIG_DIR", str(config_root))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )
    app = cli.create_app(manager_factory=lambda: manager)
    runner = CliRunner()

    set_result = runner.invoke(app, ["config", "set", "language", "zh-CN"])
    get_result = runner.invoke(app, ["config", "get", "language"])

    assert set_result.exit_code == 0
    assert get_result.exit_code == 0
    assert "zh-CN" in get_result.output
    assert '"language": "zh-CN"' in (config_root / "config.jsonc").read_text(encoding="utf-8")


def test_config_set_language_rejects_invalid_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    monkeypatch.setenv("AGENT_KIT_CONFIG_DIR", str(tmp_path / "config"))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["config", "set", "language", "fr"])

    assert result.exit_code == 1
    assert "Supported values: auto, en, zh-CN" in result.output
