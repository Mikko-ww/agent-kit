from __future__ import annotations

import importlib
import logging
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


class FakeIO:
    def __init__(self, *, text_answers=(), confirm_answers=(), select_answers=()):
        self._text_answers = deque(text_answers)
        self._confirm_answers = deque(confirm_answers)
        self._select_answers = deque(select_answers)

    def echo(self, message: str) -> None:
        typer.echo(message)

    def warn(self, message: str) -> None:
        typer.echo(message)

    def error(self, message: str) -> None:
        typer.echo(message)

    def prompt_text(self, message: str, default: str | None = None) -> str:
        if self._text_answers:
            return self._text_answers.popleft()
        if default is not None:
            return default
        raise AssertionError(f"missing text answer for: {message}")

    def confirm(self, message: str, default: bool = False) -> bool:
        if self._confirm_answers:
            return self._confirm_answers.popleft()
        return default

    def select_one(self, message: str, choices):
        if self._select_answers:
            return self._select_answers.popleft()
        if choices:
            return choices[0]
        raise AssertionError(f"missing select answer for: {message}")


def build_app(tmp_path: Path, io: FakeIO):
    plugin_cli = require_module("opencode_env_switch.plugin_cli")
    runtime = SimpleNamespace(
        logger=logging.getLogger("opencode-env-switch-test"),
        cwd=tmp_path,
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
        io=io,
    )
    return plugin_cli.build_app(runtime_factory=lambda: runtime)


def save_config(tmp_path: Path, profiles: list[dict[str, object]], *, active_profile: str | None = None, installed: bool = False):
    config_module = require_module("opencode_env_switch.config")
    config_module.save_config(
        tmp_path / "config",
        config_module.OpencodeEnvSwitchConfig(
            active_profile=active_profile,
            shells=config_module.ShellsConfig(
                zsh=config_module.ZshShellConfig(
                    rc_file=tmp_path / ".zshrc",
                    source_file=tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh",
                    installed=installed,
                )
            ),
            profiles=[
                config_module.ProfileConfig(
                    name=str(profile["name"]),
                    description=profile.get("description"),
                    opencode_config=profile.get("opencode_config"),
                    tui_config=profile.get("tui_config"),
                    config_dir=profile.get("config_dir"),
                )
                for profile in profiles
            ],
        ),
    )


def test_plugin_metadata_output():
    plugin_cli = require_module("opencode_env_switch.plugin_cli")
    result = CliRunner().invoke(plugin_cli.build_app(), ["--plugin-metadata"])

    assert result.exit_code == 0
    assert '"plugin_id": "opencode-env-switch"' in result.output
    assert '"config_version": 1' in result.output


def test_init_zsh_installs_source_block_and_writes_managed_file(tmp_path: Path):
    save_config(tmp_path, [])
    app = build_app(tmp_path, FakeIO(confirm_answers=[True]))
    runner = CliRunner()

    result = runner.invoke(app, ["init", "zsh"])

    assert result.exit_code == 0
    rc_file = tmp_path / ".zshrc"
    source_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    assert rc_file.exists()
    assert source_file.exists()
    assert 'source "' in rc_file.read_text(encoding="utf-8")
    assert "unset OPENCODE_CONFIG" in source_file.read_text(encoding="utf-8")


def test_profile_add_list_and_switch_commands_manage_profiles(tmp_path: Path):
    opencode_config = tmp_path / "work-opencode.jsonc"
    tui_config = tmp_path / "work-tui.json"
    config_dir = tmp_path / "work-dir"
    opencode_config.write_text("{}", encoding="utf-8")
    tui_config.write_text("{}", encoding="utf-8")
    config_dir.mkdir()
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    add_result = runner.invoke(
        app,
        [
            "profile",
            "add",
            "--name",
            "work",
            "--description",
            "work profile",
            "--opencode-config",
            str(opencode_config),
            "--tui-config",
            str(tui_config),
            "--config-dir",
            str(config_dir),
        ],
    )

    assert add_result.exit_code == 0

    list_result = runner.invoke(app, ["profile", "list"])
    assert list_result.exit_code == 0
    assert "[work]" in list_result.output
    assert "work profile" in list_result.output

    switch_result = runner.invoke(app, ["switch", "--name", "work"])
    assert switch_result.exit_code == 0
    assert "Switched active profile to work" in switch_result.output

    active_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    active_content = active_file.read_text(encoding="utf-8")
    assert str(opencode_config) in active_content
    assert str(tui_config) in active_content
    assert str(config_dir) in active_content


def test_switch_without_name_prompts_for_profile_selection(tmp_path: Path):
    alpha_config = tmp_path / "alpha.jsonc"
    beta_config = tmp_path / "beta.jsonc"
    alpha_config.write_text("{}", encoding="utf-8")
    beta_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [
            {"name": "alpha", "opencode_config": alpha_config},
            {"name": "beta", "opencode_config": beta_config},
        ],
    )
    app = build_app(tmp_path, FakeIO(select_answers=["beta"]))

    result = CliRunner().invoke(app, ["switch"])

    assert result.exit_code == 0
    assert "Switched active profile to beta" in result.output
    active_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    assert str(beta_config) in active_file.read_text(encoding="utf-8")


def test_switch_rejects_invalid_profile_and_keeps_old_source_file(tmp_path: Path):
    good_config = tmp_path / "good.jsonc"
    good_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [
            {"name": "good", "opencode_config": good_config},
            {"name": "broken", "opencode_config": tmp_path / "missing.jsonc"},
        ],
        active_profile="good",
    )
    active_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    active_file.write_text("export OPENCODE_CONFIG=/tmp/good.jsonc\n", encoding="utf-8")
    app = build_app(tmp_path, FakeIO())

    result = CliRunner().invoke(app, ["switch", "--name", "broken"])

    assert result.exit_code == 1
    assert "does not exist" in result.output
    assert active_file.read_text(encoding="utf-8") == "export OPENCODE_CONFIG=/tmp/good.jsonc\n"


def test_export_outputs_zsh_fragment_and_unsets_missing_variables(tmp_path: Path):
    opencode_config = tmp_path / "work.jsonc"
    opencode_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [{"name": "work", "opencode_config": opencode_config}],
    )
    app = build_app(tmp_path, FakeIO())

    result = CliRunner().invoke(app, ["export", "--name", "work", "--shell", "zsh"])

    assert result.exit_code == 0
    assert "export OPENCODE_CONFIG=" in result.output
    assert str(opencode_config) in result.output
    assert "unset OPENCODE_TUI_CONFIG" in result.output
    assert "unset OPENCODE_CONFIG_DIR" in result.output


def test_status_reports_shell_integration_and_profile_path_state(tmp_path: Path):
    opencode_config = tmp_path / "work-opencode.jsonc"
    config_dir = tmp_path / "work-dir"
    opencode_config.write_text("{}", encoding="utf-8")
    config_dir.mkdir()
    save_config(
        tmp_path,
        [{"name": "work", "opencode_config": opencode_config, "config_dir": config_dir}],
        active_profile="work",
        installed=True,
    )
    rc_file = tmp_path / ".zshrc"
    source_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    rc_file.write_text(f'# >>> agent-kit opencode-env-switch >>>\nsource "{source_file}"\n# <<< agent-kit opencode-env-switch <<<\n', encoding="utf-8")
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("unset OPENCODE_TUI_CONFIG\n", encoding="utf-8")
    app = build_app(tmp_path, FakeIO())

    result = CliRunner().invoke(app, ["status"])

    assert result.exit_code == 0
    assert "active_profile: work" in result.output
    assert "zsh_block_present: yes" in result.output
    assert "zsh_source_exists: yes" in result.output
    assert "opencode_config_valid: yes" in result.output
    assert "config_dir_valid: yes" in result.output
