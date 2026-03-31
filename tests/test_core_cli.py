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


def test_version_option_prints_core_version():
    cli = require_module("agent_kit.cli")
    agent_kit = require_module("agent_kit")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )
    app = cli.create_app(manager_factory=lambda: manager)
    expected = f"agent-kit {agent_kit.__version__}"

    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == expected

    result_short = CliRunner().invoke(app, ["-V"])
    assert result_short.exit_code == 0
    assert result_short.output.strip() == expected


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


def test_dynamic_plugin_command_forwards_help_flag():
    cli = require_module("agent_kit.cli")
    calls: list[tuple[str, list[str]]] = []
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills")
        ],
        broken_plugins=lambda: [],
        run_plugin=lambda plugin_id, args: calls.append((plugin_id, args)) or SimpleNamespace(
            returncode=0,
            stdout="Usage: agent-kit-plugin [OPTIONS] COMMAND [ARGS]...\n\nCommands:\n  status\n",
            stderr="",
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["skills-link", "--help"])

    assert result.exit_code == 0
    assert "Commands:" in result.output
    assert "status" in result.output
    assert calls == [("skills-link", ["--help"])]


def test_plugin_alias_forwards_skills_link_extra_args():
    cli = require_module("agent_kit.cli")
    calls: list[tuple[str, list[str]]] = []
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills"),
            SimpleNamespace(plugin_id="opencode-env-switch", description="Switch OpenCode env"),
        ],
        broken_plugins=lambda: [],
        run_plugin=lambda plugin_id, args: calls.append((plugin_id, args)) or SimpleNamespace(
            returncode=0,
            stdout="ok\n",
            stderr="",
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["sl", "status", "--verbose"])

    assert result.exit_code == 0
    assert calls == [("skills-link", ["status", "--verbose"])]


def test_plugin_alias_forwards_help_flag():
    cli = require_module("agent_kit.cli")
    calls: list[tuple[str, list[str]]] = []
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills"),
            SimpleNamespace(plugin_id="opencode-env-switch", description="Switch OpenCode env"),
        ],
        broken_plugins=lambda: [],
        run_plugin=lambda plugin_id, args: calls.append((plugin_id, args)) or SimpleNamespace(
            returncode=0,
            stdout="Usage: agent-kit-plugin [OPTIONS] COMMAND [ARGS]...\n\nCommands:\n  status\n",
            stderr="",
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["sl", "--help"])

    assert result.exit_code == 0
    assert "Commands:" in result.output
    assert "status" in result.output
    assert calls == [("skills-link", ["--help"])]


def test_plugin_alias_forwards_opencode_env_switch_extra_args():
    cli = require_module("agent_kit.cli")
    calls: list[tuple[str, list[str]]] = []
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills"),
            SimpleNamespace(plugin_id="opencode-env-switch", description="Switch OpenCode env"),
        ],
        broken_plugins=lambda: [],
        run_plugin=lambda plugin_id, args: calls.append((plugin_id, args)) or SimpleNamespace(
            returncode=0,
            stdout="ok\n",
            stderr="",
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["oes", "status"])

    assert result.exit_code == 0
    assert calls == [("opencode-env-switch", ["status"])]


def test_plugin_alias_forwards_self_evolve_extra_args():
    cli = require_module("agent_kit.cli")
    calls: list[tuple[str, list[str]]] = []
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills"),
            SimpleNamespace(plugin_id="opencode-env-switch", description="Switch OpenCode env"),
            SimpleNamespace(plugin_id="self-evolve", description="Self evolve"),
        ],
        broken_plugins=lambda: [],
        run_plugin=lambda plugin_id, args: calls.append((plugin_id, args)) or SimpleNamespace(
            returncode=0,
            stdout="ok\n",
            stderr="",
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["se", "status"])

    assert result.exit_code == 0
    assert calls == [("self-evolve", ["status"])]


def test_plugin_alias_preserves_plugin_usage_output_on_nonzero_exit():
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills"),
            SimpleNamespace(plugin_id="opencode-env-switch", description="Switch OpenCode env"),
        ],
        broken_plugins=lambda: [],
        run_plugin=lambda plugin_id, args: SimpleNamespace(
            returncode=2,
            stdout="Usage: agent-kit-plugin init [OPTIONS] COMMAND [ARGS]...\n\nCommands:\n  zsh\n",
            stderr="",
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["oes", "init"])

    assert result.exit_code == 2
    assert "Usage: agent-kit-plugin init" in result.output
    assert "zsh" in result.output
    assert "unknown command failure" not in result.output


def test_root_help_shows_plugin_alias_hints_but_hides_alias_commands():
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills"),
            SimpleNamespace(plugin_id="opencode-env-switch", description="Switch OpenCode env"),
            SimpleNamespace(plugin_id="self-evolve", description="Self evolve"),
        ],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "skills-link" in result.output
    assert "sl）" in result.output
    assert "opencode-env-switch" in result.output
    assert "oes）" in result.output
    assert "self-evolve" in result.output
    assert "se）" in result.output
    assert "\n│ sl " not in result.output
    assert "\n│ oes " not in result.output
    assert "\n│ se " not in result.output


def test_plugin_alias_is_not_registered_for_unavailable_plugin():
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills")
        ],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["oes", "status"])

    assert result.exit_code == 2


def test_create_app_rejects_plugin_alias_conflict_with_plugin_id():
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills"),
            SimpleNamespace(plugin_id="sl", description="Conflicting plugin"),
        ],
        broken_plugins=lambda: [],
    )

    with pytest.raises(ValueError, match="plugin alias conflict"):
        cli.create_app(manager_factory=lambda: manager)


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


def test_plugins_info_uses_dash_for_missing_optional_git_fields():
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
            tag="skills-link-v0.2.0",
            commit=None,
            status="installed",
            config_path=Path("/tmp/config.jsonc"),
            venv_path=Path("/tmp/venv"),
        ),
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["plugins", "info", "skills-link"])

    assert result.exit_code == 0
    assert "tag: skills-link-v0.2.0" in result.output
    assert "commit: -" in result.output


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
    assert "显示 agent-kit 版本并退出。" in result.output


def test_main_returns_one_when_plugin_error_occurs(monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    messages: list[str] = []

    def fake_app():
        def runner():
            raise require_module("agent_kit.plugin_manager").PluginError("boom")

        return runner

    monkeypatch.setattr(cli, "create_app", fake_app)
    monkeypatch.setattr(cli.typer, "secho", lambda message, **kwargs: messages.append(message))

    result = cli.main()

    assert result == 1
    assert messages
    assert "boom" in messages[0]


def test_root_help_uses_zh_cn_plugin_alias_hint_when_config_requests_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    cli = require_module("agent_kit.cli")
    config_root = tmp_path / "config"
    config_root.mkdir(parents=True)
    (config_root / "config.jsonc").write_text(
        json.dumps({"language": "zh-CN"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_KIT_CONFIG_DIR", str(config_root))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [
            SimpleNamespace(plugin_id="skills-link", description="Link local skills")
        ],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "运行 skills-link 插件命令。（别名：sl）" in result.output


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


def test_config_list_shows_supported_global_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    monkeypatch.setenv("AGENT_KIT_CONFIG_DIR", str(tmp_path / "config"))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["config", "list"])

    assert result.exit_code == 0
    assert "language" in result.output
    assert "auto, en, zh-CN" in result.output


def test_config_set_language_auto_keeps_empty_template_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    config_root = tmp_path / "config"
    monkeypatch.setenv("AGENT_KIT_CONFIG_DIR", str(config_root))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    runner = CliRunner()

    set_result = runner.invoke(app, ["config", "set", "language", "en"])
    reset_result = runner.invoke(app, ["config", "set", "language", "auto"])

    assert set_result.exit_code == 0
    assert reset_result.exit_code == 0
    assert (config_root / "config.jsonc").read_text(encoding="utf-8") == "{\n  // Add global CLI settings here.\n}\n"


def test_alias_enable_creates_managed_wrapper_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    cli = require_module("agent_kit.cli")
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )
    app = cli.create_app(manager_factory=lambda: manager)
    runner = CliRunner()

    first_result = runner.invoke(app, ["alias", "enable"])
    second_result = runner.invoke(app, ["alias", "enable"])

    alias_path = home / ".local" / "bin" / "ak"
    assert first_result.exit_code == 0
    assert second_result.exit_code == 0
    assert alias_path.exists()
    assert alias_path.read_text(encoding="utf-8").startswith("#!/usr/bin/env sh\n")
    assert "agent-kit managed alias" in alias_path.read_text(encoding="utf-8")
    assert 'exec agent-kit "$@"' in alias_path.read_text(encoding="utf-8")
    assert alias_path.stat().st_mode & 0o111


def test_alias_enable_rejects_existing_unmanaged_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    home = tmp_path / "home"
    alias_dir = home / ".local" / "bin"
    alias_dir.mkdir(parents=True)
    (alias_dir / "ak").write_text("#!/usr/bin/env sh\necho custom\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["alias", "enable"])

    assert result.exit_code == 1
    assert "not managed by agent-kit" in result.output


def test_alias_disable_removes_managed_wrapper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )
    app = cli.create_app(manager_factory=lambda: manager)
    runner = CliRunner()

    enable_result = runner.invoke(app, ["alias", "enable"])
    disable_result = runner.invoke(app, ["alias", "disable"])

    assert enable_result.exit_code == 0
    assert disable_result.exit_code == 0
    assert not (home / ".local" / "bin" / "ak").exists()


def test_alias_disable_rejects_existing_unmanaged_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    home = tmp_path / "home"
    alias_dir = home / ".local" / "bin"
    alias_dir.mkdir(parents=True)
    (alias_dir / "ak").write_text("#!/usr/bin/env sh\necho custom\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["alias", "disable"])

    assert result.exit_code == 1
    assert "not managed by agent-kit" in result.output


def test_alias_status_reports_enabled_state_and_path_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )
    app = cli.create_app(manager_factory=lambda: manager)
    runner = CliRunner()

    enable_result = runner.invoke(app, ["alias", "enable"])
    status_result = runner.invoke(app, ["alias", "status"])

    assert enable_result.exit_code == 0
    assert status_result.exit_code == 0
    assert "status: enabled" in status_result.output
    assert str(home / ".local" / "bin" / "ak") in status_result.output
    assert "not in PATH" in status_result.output


def test_alias_status_reports_disabled_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cli = require_module("agent_kit.cli")
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["alias", "status"])

    assert result.exit_code == 0
    assert "status: disabled" in result.output


def test_help_lists_alias_namespace():
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(
        runnable_plugins=lambda: [],
        broken_plugins=lambda: [],
    )

    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "alias" in result.output


def test_alias_help_uses_zh_cn_when_config_requests_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
    result = CliRunner().invoke(app, ["alias", "--help"])

    assert result.exit_code == 0
    assert "管理 agent-kit CLI 别名。" in result.output
