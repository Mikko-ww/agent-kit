from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def test_save_and_load_config_round_trip(tmp_path: Path):
    config_module = require_module("opencode_env_switch.config")

    config = config_module.OpencodeEnvSwitchConfig(
        active_profile="work",
        shells=config_module.ShellsConfig(
            zsh=config_module.ZshShellConfig(
                rc_file=tmp_path / ".zshrc",
                source_file=tmp_path / "config" / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh",
                installed=True,
            )
        ),
        profiles=[
            config_module.ProfileConfig(
                name="work",
                description="work profile",
                opencode_config=tmp_path / "work-opencode.jsonc",
                tui_config=tmp_path / "work-tui.json",
                config_dir=tmp_path / "work-dir",
            )
        ],
    )
    config.profiles[0].opencode_config.write_text("{}", encoding="utf-8")
    config.profiles[0].tui_config.write_text("{}", encoding="utf-8")
    config.profiles[0].config_dir.mkdir()

    saved_path = config_module.save_config(tmp_path / "agent-kit", config)
    loaded = config_module.load_config(tmp_path / "agent-kit")

    assert loaded == config
    assert saved_path == config_module.config_file_path(tmp_path / "agent-kit")
    assert '"plugin_id": "opencode-env-switch"' in saved_path.read_text(encoding="utf-8")


def test_render_zsh_env_exports_present_values_and_unsets_missing(tmp_path: Path):
    config_module = require_module("opencode_env_switch.config")
    logic_module = require_module("opencode_env_switch.logic")
    opencode_config = tmp_path / "opencode.jsonc"
    config_dir = tmp_path / "config-dir"
    opencode_config.write_text("{}", encoding="utf-8")
    config_dir.mkdir()
    profile = config_module.ProfileConfig(
        name="work",
        description=None,
        opencode_config=opencode_config,
        tui_config=None,
        config_dir=config_dir,
    )

    rendered = logic_module.render_zsh_env(profile)

    assert "export OPENCODE_CONFIG=" in rendered
    assert str(opencode_config) in rendered
    assert "unset OPENCODE_TUI_CONFIG" in rendered
    assert "export OPENCODE_CONFIG_DIR=" in rendered
    assert str(config_dir) in rendered


def test_install_or_update_zsh_integration_is_idempotent(tmp_path: Path):
    logic_module = require_module("opencode_env_switch.logic")
    rc_file = tmp_path / ".zshrc"
    source_file = tmp_path / "active.zsh"
    rc_file.write_text("export PATH=/usr/bin\n", encoding="utf-8")

    logic_module.install_or_update_zsh_integration(rc_file, source_file)
    logic_module.install_or_update_zsh_integration(rc_file, source_file)

    content = rc_file.read_text(encoding="utf-8")
    assert "export PATH=/usr/bin" in content
    assert content.count(logic_module.ZSH_MARKER_BEGIN) == 1
    assert content.count(logic_module.ZSH_MARKER_END) == 1
    assert f'source "{source_file}"' in content


def test_remove_profile_rejects_active_profile(tmp_path: Path):
    config_module = require_module("opencode_env_switch.config")
    logic_module = require_module("opencode_env_switch.logic")
    config = config_module.OpencodeEnvSwitchConfig(
        active_profile="work",
        shells=config_module.ShellsConfig(
            zsh=config_module.ZshShellConfig(
                rc_file=tmp_path / ".zshrc",
                source_file=tmp_path / "active.zsh",
                installed=False,
            )
        ),
        profiles=[
            config_module.ProfileConfig(
                name="work",
                description=None,
                opencode_config=tmp_path / "work.jsonc",
                tui_config=None,
                config_dir=None,
            )
        ],
    )

    with pytest.raises(ValueError, match="active profile"):
        logic_module.remove_profile(config, "work")

