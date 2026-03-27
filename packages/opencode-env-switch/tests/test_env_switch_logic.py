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


def test_create_profile_directory_creates_all_three(tmp_path: Path):
    logic_module = require_module("opencode_env_switch.logic")
    config_module = require_module("opencode_env_switch.config")
    config_root = tmp_path / "config"

    result = logic_module.create_profile_directory(
        config_root,
        "work",
        create_opencode_config=True,
        create_tui_config=True,
        create_config_dir=True,
    )

    assert result.opencode_config is not None
    assert result.tui_config is not None
    assert result.config_dir is not None
    assert result.opencode_config.exists() and result.opencode_config.is_file()
    assert result.tui_config.exists() and result.tui_config.is_file()
    assert result.config_dir.exists() and result.config_dir.is_dir()
    assert result.opencode_config.name == "opencode.jsonc"
    assert result.tui_config.name == "tui.json"
    expected_profile_dir = config_module.profiles_base_path(config_root) / "work"
    assert result.config_dir == expected_profile_dir
    assert not (expected_profile_dir / "config").exists()
    assert "OpenCode configuration" in result.opencode_config.read_text(encoding="utf-8")
    assert result.tui_config.read_text(encoding="utf-8").strip() == "{}"


def test_create_profile_directory_partial(tmp_path: Path):
    logic_module = require_module("opencode_env_switch.logic")
    config_root = tmp_path / "config"

    result = logic_module.create_profile_directory(
        config_root,
        "dev",
        create_opencode_config=True,
        create_tui_config=False,
        create_config_dir=False,
    )

    assert result.opencode_config is not None and result.opencode_config.exists()
    assert result.tui_config is None
    assert result.config_dir is None


def test_create_profile_directory_rejects_existing(tmp_path: Path):
    logic_module = require_module("opencode_env_switch.logic")
    config_module = require_module("opencode_env_switch.config")
    config_root = tmp_path / "config"
    profile_dir = config_module.profiles_base_path(config_root) / "existing"
    profile_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="already exists"):
        logic_module.create_profile_directory(
            config_root, "existing", create_opencode_config=True,
        )


def test_ensure_managed_profile_paths_reuses_existing_files_without_overwriting(tmp_path: Path):
    logic_module = require_module("opencode_env_switch.logic")
    config_module = require_module("opencode_env_switch.config")
    config_root = tmp_path / "config"
    profile_dir = config_module.profiles_base_path(config_root) / "work"
    profile_dir.mkdir(parents=True)
    existing_opencode = profile_dir / "opencode.jsonc"
    existing_opencode.write_text('{"custom": true}\n', encoding="utf-8")

    result = logic_module.ensure_managed_profile_paths(
        config_root,
        "work",
        create_opencode_config=True,
        create_tui_config=True,
        create_config_dir=True,
    )

    assert result.opencode_config == existing_opencode
    assert existing_opencode.read_text(encoding="utf-8") == '{"custom": true}\n'
    assert result.tui_config is not None and result.tui_config.exists()
    assert result.config_dir is not None and result.config_dir.exists()
    assert result.config_dir == profile_dir
    assert not (profile_dir / "config").exists()


def test_add_profile_rejects_reserved_name_default(tmp_path: Path):
    config_module = require_module("opencode_env_switch.config")
    logic_module = require_module("opencode_env_switch.logic")
    oc = tmp_path / "x.jsonc"
    oc.write_text("{}", encoding="utf-8")
    base = config_module.OpencodeEnvSwitchConfig(
        active_profile=None,
        shells=config_module.ShellsConfig(
            zsh=config_module.ZshShellConfig(
                rc_file=tmp_path / ".zshrc",
                source_file=tmp_path / "active.zsh",
                installed=False,
            )
        ),
        profiles=[],
    )
    profile = config_module.ProfileConfig(
        name="default",
        description=None,
        opencode_config=oc,
        tui_config=None,
        config_dir=None,
    )
    with pytest.raises(ValueError, match="reserved"):
        logic_module.add_profile(base, profile)


def test_activate_profile_accepts_virtual_default(tmp_path: Path):
    config_module = require_module("opencode_env_switch.config")
    logic_module = require_module("opencode_env_switch.logic")
    oc = tmp_path / "x.jsonc"
    oc.write_text("{}", encoding="utf-8")
    cfg = config_module.OpencodeEnvSwitchConfig(
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
                opencode_config=oc,
                tui_config=None,
                config_dir=None,
            )
        ],
    )
    updated = logic_module.activate_profile(cfg, "default")
    assert updated.active_profile == "default"


def test_save_and_load_round_trip_active_default_no_profiles(tmp_path: Path):
    config_module = require_module("opencode_env_switch.config")
    root = tmp_path / "agent-kit"
    cfg = config_module.OpencodeEnvSwitchConfig(
        active_profile="default",
        shells=config_module.ShellsConfig(
            zsh=config_module.ZshShellConfig(
                rc_file=tmp_path / ".zshrc",
                source_file=root / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh",
                installed=False,
            )
        ),
        profiles=[],
    )
    config_module.save_config(root, cfg)
    loaded = config_module.load_config(root)
    assert loaded is not None
    assert loaded.active_profile == "default"
    assert loaded.profiles == []


def test_load_config_rejects_user_profile_named_default(tmp_path: Path):
    config_module = require_module("opencode_env_switch.config")
    root = tmp_path / "agent-kit"
    oc = tmp_path / "legacy.jsonc"
    oc.write_text("{}", encoding="utf-8")
    path = config_module.config_file_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "{",
                '  "plugin_id": "opencode-env-switch",',
                '  "config_version": 1,',
                '  "active_profile": null,',
                '  "shells": {',
                '    "zsh": {',
                f'      "rc_file": "{tmp_path / ".zshrc"}",',
                f'      "source_file": "{root / "plugins" / "opencode-env-switch" / "zsh" / "active.zsh"}",',
                '      "installed": false',
                "    }",
                "  },",
                '  "profiles": [',
                "    {",
                '      "name": "default",',
                f'      "opencode_config": "{oc}"',
                "    }",
                "  ]",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    assert config_module.load_config(root) is None


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

