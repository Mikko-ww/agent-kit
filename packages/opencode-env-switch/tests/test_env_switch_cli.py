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
        default_zsh_rc_file=tmp_path / ".zshrc",
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


def test_help_uses_zh_cn_for_root_and_profile_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    root_help = runner.invoke(app, ["--help"])
    profile_help = runner.invoke(app, ["profile", "--help"])

    assert root_help.exit_code == 0
    assert "通过受管 shell 环境文件切换 OpenCode profile。" in root_help.output
    assert "查看当前受管状态和 profile 路径状态。" in root_help.output
    assert profile_help.exit_code == 0
    assert "管理 OpenCode profiles。" in profile_help.output
    assert "新增一个 OpenCode profile。" in profile_help.output


def test_init_zsh_installs_source_block_and_writes_managed_file(tmp_path: Path):
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


def test_profile_list_warning_and_export_error_use_zh_cn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    list_result = runner.invoke(app, ["profile", "list"])
    export_result = runner.invoke(app, ["export", "--shell", "bash"])

    assert list_result.exit_code == 0
    assert "当前没有配置任何 profile。" in list_result.output
    assert export_result.exit_code == 1
    assert "不支持的 shell: bash" in export_result.output


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


def test_switch_to_default_unsets_opencode_vars(tmp_path: Path):
    opencode_config = tmp_path / "work-opencode.jsonc"
    opencode_config.write_text("{}", encoding="utf-8")
    save_config(tmp_path, [{"name": "work", "opencode_config": opencode_config}], active_profile="work")
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    result = runner.invoke(app, ["switch", "--name", "default"])

    assert result.exit_code == 0
    assert "Switched active profile to default" in result.output
    active_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    content = active_file.read_text(encoding="utf-8")
    assert "unset OPENCODE_CONFIG" in content
    assert "unset OPENCODE_TUI_CONFIG" in content
    assert "unset OPENCODE_CONFIG_DIR" in content
    config_module = require_module("opencode_env_switch.config")
    loaded = config_module.load_config(tmp_path / "config")
    assert loaded is not None
    assert loaded.active_profile == "default"


def test_switch_default_works_without_user_profiles(tmp_path: Path):
    save_config(tmp_path, [], active_profile=None)
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    result = runner.invoke(app, ["switch", "--name", "default"])

    assert result.exit_code == 0
    active_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    assert "unset OPENCODE_CONFIG" in active_file.read_text(encoding="utf-8")


def test_export_default_prints_unsets(tmp_path: Path):
    save_config(tmp_path, [], active_profile=None)
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    result = runner.invoke(app, ["export", "--name", "default", "--shell", "zsh"])

    assert result.exit_code == 0
    assert "unset OPENCODE_CONFIG" in result.output


def test_profile_add_rejects_reserved_name_default(tmp_path: Path):
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["profile", "add", "--name", "default", "--auto-create"],
    )

    assert result.exit_code == 1
    assert "reserved" in result.output


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


def test_profile_add_auto_create_creates_all_files(tmp_path: Path):
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["profile", "add", "--name", "work", "--auto-create"],
    )

    assert result.exit_code == 0
    profiles_dir = tmp_path / "config" / "plugins" / "opencode-env-switch" / "profiles" / "work"
    assert profiles_dir.exists()
    assert (profiles_dir / "opencode.jsonc").is_file()
    assert (profiles_dir / "tui.json").is_file()
    assert not (profiles_dir / "config").exists()
    config_module = require_module("opencode_env_switch.config")
    loaded = config_module.load_config(tmp_path / "config")
    work = next(p for p in loaded.profiles if p.name == "work")
    assert work.config_dir == profiles_dir
    assert "Created profile directory" in result.output


def test_profile_add_auto_create_mixed_with_manual_path(tmp_path: Path):
    tui_config = tmp_path / "my-tui.json"
    tui_config.write_text("{}", encoding="utf-8")
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "profile", "add",
            "--name", "mixed",
            "--auto-create",
            "--tui-config", str(tui_config),
        ],
    )

    assert result.exit_code == 0
    profiles_dir = tmp_path / "config" / "plugins" / "opencode-env-switch" / "profiles" / "mixed"
    assert (profiles_dir / "opencode.jsonc").is_file()
    assert not (profiles_dir / "tui.json").exists()
    assert not (profiles_dir / "config").exists()
    config_module = require_module("opencode_env_switch.config")
    mixed = next(p for p in config_module.load_config(tmp_path / "config").profiles if p.name == "mixed")
    assert mixed.config_dir == profiles_dir


def test_profile_add_auto_create_rollback_on_duplicate_name(tmp_path: Path):
    opencode_config = tmp_path / "existing.jsonc"
    opencode_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [{"name": "dupe", "opencode_config": opencode_config}],
    )
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["profile", "add", "--name", "dupe", "--auto-create"],
    )

    assert result.exit_code == 1
    profiles_dir = tmp_path / "config" / "plugins" / "opencode-env-switch" / "profiles" / "dupe"
    assert not profiles_dir.exists()


def test_profile_add_interactive_auto_create_single_path(tmp_path: Path):
    auto_label = "Auto-create (recommended)"
    skip_label = "Skip"
    app = build_app(
        tmp_path,
        FakeIO(
            text_answers=["myprofile"],
            select_answers=[auto_label, skip_label, skip_label],
        ),
    )
    runner = CliRunner()

    result = runner.invoke(app, ["profile", "add"])

    assert result.exit_code == 0
    profiles_dir = tmp_path / "config" / "plugins" / "opencode-env-switch" / "profiles" / "myprofile"
    assert (profiles_dir / "opencode.jsonc").is_file()
    assert not (profiles_dir / "tui.json").exists()
    assert not (profiles_dir / "config").exists()


def test_wizard_auto_create_mode(tmp_path: Path):
    auto_mode_label = "Auto-create (recommended) - generate config files under managed directory"
    app = build_app(
        tmp_path,
        FakeIO(
            text_answers=["testprofile", ""],
            confirm_answers=[
                True,   # create opencode_config
                True,   # create tui_config
                True,   # create config_dir
            ],
            select_answers=["Add profile", auto_mode_label],
        ),
    )
    runner = CliRunner()

    result = runner.invoke(app, ["wizard"])

    assert result.exit_code == 0
    profiles_dir = tmp_path / "config" / "plugins" / "opencode-env-switch" / "profiles" / "testprofile"
    assert profiles_dir.exists()
    assert (profiles_dir / "opencode.jsonc").is_file()
    assert (profiles_dir / "tui.json").is_file()
    assert not (profiles_dir / "config").exists()
    config_module = require_module("opencode_env_switch.config")
    tp = next(p for p in config_module.load_config(tmp_path / "config").profiles if p.name == "testprofile")
    assert tp.config_dir == profiles_dir
    assert "Setup completed" in result.output


def test_wizard_manual_mode_still_works(tmp_path: Path):
    opencode_config = tmp_path / "manual.jsonc"
    opencode_config.write_text("{}", encoding="utf-8")
    manual_mode_label = "Enter existing paths - specify paths to existing config files"
    app = build_app(
        tmp_path,
        FakeIO(
            text_answers=["manual-profile", "", str(opencode_config), "", ""],
            select_answers=["Add profile", manual_mode_label],
        ),
    )
    runner = CliRunner()

    result = runner.invoke(app, ["wizard"])

    assert result.exit_code == 0
    assert "Setup completed" in result.output


def test_wizard_runs_directly_without_default_subcommand(tmp_path: Path):
    add_label = "Add profile"
    app = build_app(
        tmp_path,
        FakeIO(
            text_answers=["direct-profile", ""],
            confirm_answers=[True, True, True, True],
            select_answers=[
                add_label,
                "Auto-create (recommended) - generate config files under managed directory",
            ],
        ),
    )

    result = CliRunner().invoke(app, ["wizard"])

    assert result.exit_code == 0
    profiles_dir = tmp_path / "config" / "plugins" / "opencode-env-switch" / "profiles" / "direct-profile"
    assert profiles_dir.exists()


def test_wizard_add_profile_preserves_existing_profiles(tmp_path: Path):
    first_config = tmp_path / "first.jsonc"
    first_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [{"name": "first", "opencode_config": first_config}],
        active_profile="first",
    )
    add_label = "Add profile"
    app = build_app(
        tmp_path,
        FakeIO(
            text_answers=["second", ""],
            confirm_answers=[True, False, False, True],
            select_answers=[
                add_label,
                "Auto-create (recommended) - generate config files under managed directory",
            ],
        ),
    )

    result = CliRunner().invoke(app, ["wizard"])

    assert result.exit_code == 0
    config_module = require_module("opencode_env_switch.config")
    loaded = config_module.load_config(tmp_path / "config")
    assert loaded is not None
    assert [profile.name for profile in loaded.profiles] == ["first", "second"]
    assert loaded.active_profile == "first"


def test_wizard_can_switch_active_profile_from_menu(tmp_path: Path):
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
        active_profile="alpha",
    )
    app = build_app(
        tmp_path,
        FakeIO(select_answers=["Switch active profile", "beta"]),
    )

    result = CliRunner().invoke(app, ["wizard"])

    assert result.exit_code == 0
    config_module = require_module("opencode_env_switch.config")
    loaded = config_module.load_config(tmp_path / "config")
    assert loaded is not None
    assert loaded.active_profile == "beta"


def test_wizard_menu_selection_is_stable_under_zh_locale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AGENT_KIT_LANG", raising=False)
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
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
        active_profile="alpha",
    )
    app = build_app(
        tmp_path,
        FakeIO(select_answers=["Switch active profile", "beta"]),
    )

    result = CliRunner().invoke(app, ["wizard"])

    assert result.exit_code == 0
    config_module = require_module("opencode_env_switch.config")
    loaded = config_module.load_config(tmp_path / "config")
    assert loaded is not None
    assert loaded.active_profile == "beta"


def test_wizard_can_update_existing_profile_description(tmp_path: Path):
    work_config = tmp_path / "work.jsonc"
    work_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [{"name": "work", "description": "old", "opencode_config": work_config}],
        active_profile="work",
    )
    app = build_app(
        tmp_path,
        FakeIO(
            text_answers=["updated description"],
            select_answers=["Update existing profile", "work", "Keep current paths"],
        ),
    )

    result = CliRunner().invoke(app, ["wizard"])

    assert result.exit_code == 0
    config_module = require_module("opencode_env_switch.config")
    loaded = config_module.load_config(tmp_path / "config")
    assert loaded is not None
    assert loaded.profiles[0].description == "updated description"
    assert loaded.profiles[0].opencode_config == work_config


def test_wizard_can_repair_zsh_from_menu(tmp_path: Path):
    profile_config = tmp_path / "work.jsonc"
    profile_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [{"name": "work", "opencode_config": profile_config}],
        active_profile="work",
        installed=False,
    )
    app = build_app(
        tmp_path,
        FakeIO(select_answers=["Initialize or repair zsh integration"]),
    )

    result = CliRunner().invoke(app, ["wizard"])

    assert result.exit_code == 0
    source_file = tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"
    rc_file = tmp_path / ".zshrc"
    assert source_file.exists()
    assert rc_file.exists()
    assert str(profile_config) in source_file.read_text(encoding="utf-8")


def test_wizard_can_show_status_and_exit(tmp_path: Path):
    profile_config = tmp_path / "work.jsonc"
    profile_config.write_text("{}", encoding="utf-8")
    save_config(
        tmp_path,
        [{"name": "work", "opencode_config": profile_config}],
        active_profile="work",
    )
    app = build_app(
        tmp_path,
        FakeIO(select_answers=["Show current status and exit"]),
    )

    result = CliRunner().invoke(app, ["wizard"])

    assert result.exit_code == 0
    assert "active_profile: work" in result.output
    assert "[work]" in result.output


def test_wizard_default_subcommand_is_removed(tmp_path: Path):
    app = build_app(tmp_path, FakeIO())

    result = CliRunner().invoke(app, ["wizard", "default"])

    assert result.exit_code != 0


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
