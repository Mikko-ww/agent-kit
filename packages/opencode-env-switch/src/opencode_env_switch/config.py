from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from opencode_env_switch import CONFIG_VERSION, PLUGIN_ID
from opencode_env_switch.jsonc import load_jsonc, write_jsonc

PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# 虚拟切换目标：写入 active.zsh 时 unset 全部 OPENCODE_*，恢复 shell 默认行为（不经由本插件覆盖）
SYSTEM_DEFAULT_PROFILE_NAME = "default"


def is_system_default_profile_name(name: str) -> bool:
    return name == SYSTEM_DEFAULT_PROFILE_NAME


def validate_user_profile_name_for_register(name: str) -> None:
    """用户自定义 profile 注册前校验：合法 pattern 且不得占用保留名 default。"""
    if not isinstance(name, str) or not PROFILE_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"invalid profile name: {name}")
    if is_system_default_profile_name(name):
        raise ValueError(
            f"profile name '{SYSTEM_DEFAULT_PROFILE_NAME}' is reserved for system OpenCode environment"
        )


@dataclass(slots=True, frozen=True)
class ProfileConfig:
    name: str
    description: str | None
    opencode_config: Path | None
    tui_config: Path | None
    config_dir: Path | None


@dataclass(slots=True, frozen=True)
class ZshShellConfig:
    rc_file: Path
    source_file: Path
    installed: bool


@dataclass(slots=True, frozen=True)
class ShellsConfig:
    zsh: ZshShellConfig


@dataclass(slots=True, frozen=True)
class OpencodeEnvSwitchConfig:
    active_profile: str | None
    shells: ShellsConfig
    profiles: list[ProfileConfig]


def config_file_path(config_root: Path) -> Path:
    return config_root / "plugins" / PLUGIN_ID / "config.jsonc"


def profiles_base_path(config_root: Path) -> Path:
    return config_root / "plugins" / PLUGIN_ID / "profiles"


def default_zsh_source_file(config_root: Path) -> Path:
    return config_root / "plugins" / PLUGIN_ID / "zsh" / "active.zsh"


def default_config(config_root: Path, *, zsh_rc_file: Path | None = None) -> OpencodeEnvSwitchConfig:
    return OpencodeEnvSwitchConfig(
        active_profile=None,
        shells=ShellsConfig(
            zsh=ZshShellConfig(
                rc_file=(zsh_rc_file or Path("~/.zshrc").expanduser()),
                source_file=default_zsh_source_file(config_root),
                installed=False,
            )
        ),
        profiles=[],
    )


def load_config(config_root: Path) -> OpencodeEnvSwitchConfig | None:
    path = config_file_path(config_root)
    if not path.exists():
        return None

    data = load_jsonc(path)
    if not data:
        return None

    if data.get("config_version") != CONFIG_VERSION:
        return None

    shells_data = data.get("shells")
    zsh_data = shells_data.get("zsh") if isinstance(shells_data, dict) else None
    if not isinstance(zsh_data, dict):
        return None

    rc_file = zsh_data.get("rc_file")
    source_file = zsh_data.get("source_file")
    installed = zsh_data.get("installed")
    if not rc_file or not source_file or not isinstance(installed, bool):
        return None

    profiles_data = data.get("profiles")
    if not isinstance(profiles_data, list):
        return None

    profiles: list[ProfileConfig] = []
    seen_names: set[str] = set()
    for item in profiles_data:
        if not isinstance(item, dict):
            return None
        name = item.get("name")
        description = item.get("description")
        profile = ProfileConfig(
            name=str(name) if name is not None else "",
            description=str(description) if description is not None else None,
            opencode_config=_optional_path(item.get("opencode_config")),
            tui_config=_optional_path(item.get("tui_config")),
            config_dir=_optional_path(item.get("config_dir")),
        )
        if not _is_valid_profile_name(profile.name) or profile.name in seen_names:
            return None
        if not _profile_has_paths(profile):
            return None
        seen_names.add(profile.name)
        profiles.append(profile)

    active_profile = data.get("active_profile")
    if active_profile is not None:
        if not isinstance(active_profile, str):
            return None
        if active_profile != SYSTEM_DEFAULT_PROFILE_NAME and active_profile not in seen_names:
            return None

    return OpencodeEnvSwitchConfig(
        active_profile=active_profile,
        shells=ShellsConfig(
            zsh=ZshShellConfig(
                rc_file=Path(str(rc_file)).expanduser(),
                source_file=Path(str(source_file)).expanduser(),
                installed=installed,
            )
        ),
        profiles=profiles,
    )


def save_config(config_root: Path, config: OpencodeEnvSwitchConfig) -> Path:
    _validate_config(config)
    return write_jsonc(
        config_file_path(config_root),
        {
            "plugin_id": PLUGIN_ID,
            "config_version": CONFIG_VERSION,
            "active_profile": config.active_profile,
            "shells": {
                "zsh": {
                    "rc_file": str(config.shells.zsh.rc_file),
                    "source_file": str(config.shells.zsh.source_file),
                    "installed": config.shells.zsh.installed,
                }
            },
            "profiles": [_profile_to_dict(profile) for profile in config.profiles],
        },
    )


def _profile_to_dict(profile: ProfileConfig) -> dict[str, object]:
    data: dict[str, object] = {"name": profile.name}
    if profile.description is not None:
        data["description"] = profile.description
    if profile.opencode_config is not None:
        data["opencode_config"] = str(profile.opencode_config)
    if profile.tui_config is not None:
        data["tui_config"] = str(profile.tui_config)
    if profile.config_dir is not None:
        data["config_dir"] = str(profile.config_dir)
    return data


def _validate_config(config: OpencodeEnvSwitchConfig) -> None:
    seen_names: set[str] = set()
    for profile in config.profiles:
        if not _is_valid_profile_name(profile.name):
            raise ValueError(f"invalid profile name: {profile.name}")
        if profile.name in seen_names:
            raise ValueError(f"duplicate profile name: {profile.name}")
        if not _profile_has_paths(profile):
            raise ValueError(f"profile must define at least one path: {profile.name}")
        seen_names.add(profile.name)

    if config.active_profile is not None:
        if is_system_default_profile_name(config.active_profile):
            pass
        elif config.active_profile not in seen_names:
            raise ValueError(f"unknown active profile: {config.active_profile}")


def _profile_has_paths(profile: ProfileConfig) -> bool:
    return any(
        path is not None
        for path in (profile.opencode_config, profile.tui_config, profile.config_dir)
    )


def _optional_path(value: object | None) -> Path | None:
    if value is None:
        return None
    return Path(str(value)).expanduser()


def _is_valid_profile_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and bool(PROFILE_NAME_PATTERN.fullmatch(name))
        and not is_system_default_profile_name(name)
    )
