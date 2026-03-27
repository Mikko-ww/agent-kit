from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re

from opencode_env_switch.config import (
    OpencodeEnvSwitchConfig,
    ProfileConfig,
    ShellsConfig,
    ZshShellConfig,
    is_system_default_profile_name,
    profiles_base_path,
    validate_user_profile_name_for_register,
)

OPENCODE_CONFIG_TEMPLATE = """\
// OpenCode configuration file
// See https://opencode.ai for documentation
{
  // Add your OpenCode configuration here
}
"""

TUI_CONFIG_TEMPLATE = "{}\n"

ZSH_MARKER_BEGIN = "# >>> agent-kit opencode-env-switch >>>"
ZSH_MARKER_END = "# <<< agent-kit opencode-env-switch <<<"
ZSH_BLOCK_PATTERN = re.compile(
    rf"{re.escape(ZSH_MARKER_BEGIN)}\n.*?\n{re.escape(ZSH_MARKER_END)}\n?",
    re.DOTALL,
)


@dataclass(slots=True, frozen=True)
class OptionalPathStatus:
    label: str
    path: Path | None
    valid: bool | None
    error: str | None


@dataclass(slots=True, frozen=True)
class ZshIntegrationStatus:
    rc_exists: bool
    block_present: bool
    source_exists: bool


@dataclass(slots=True, frozen=True)
class AutoCreateResult:
    opencode_config: Path | None
    tui_config: Path | None
    config_dir: Path | None


def create_profile_directory(
    config_root: Path,
    profile_name: str,
    *,
    create_opencode_config: bool = False,
    create_tui_config: bool = False,
    create_config_dir: bool = False,
) -> AutoCreateResult:
    profile_dir = profiles_base_path(config_root) / profile_name
    if profile_dir.exists():
        raise ValueError(f"profile directory already exists: {profile_dir}")

    profile_dir.mkdir(parents=True, exist_ok=True)

    opencode_config_path: Path | None = None
    tui_config_path: Path | None = None
    config_dir_path: Path | None = None

    if create_opencode_config:
        opencode_config_path = profile_dir / "opencode.jsonc"
        opencode_config_path.write_text(OPENCODE_CONFIG_TEMPLATE, encoding="utf-8")

    if create_tui_config:
        tui_config_path = profile_dir / "tui.json"
        tui_config_path.write_text(TUI_CONFIG_TEMPLATE, encoding="utf-8")

    if create_config_dir:
        # 自动创建模式下 OPENCODE_CONFIG_DIR 指向 profile 根目录，不再额外建 profiles/<name>/config/
        config_dir_path = profile_dir

    return AutoCreateResult(
        opencode_config=opencode_config_path,
        tui_config=tui_config_path,
        config_dir=config_dir_path,
    )


def ensure_managed_profile_paths(
    config_root: Path,
    profile_name: str,
    *,
    create_opencode_config: bool = False,
    create_tui_config: bool = False,
    create_config_dir: bool = False,
) -> AutoCreateResult:
    profile_dir = profiles_base_path(config_root) / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    opencode_config_path: Path | None = None
    tui_config_path: Path | None = None
    config_dir_path: Path | None = None

    if create_opencode_config:
        opencode_config_path = profile_dir / "opencode.jsonc"
        if not opencode_config_path.exists():
            opencode_config_path.write_text(OPENCODE_CONFIG_TEMPLATE, encoding="utf-8")

    if create_tui_config:
        tui_config_path = profile_dir / "tui.json"
        if not tui_config_path.exists():
            tui_config_path.write_text(TUI_CONFIG_TEMPLATE, encoding="utf-8")

    if create_config_dir:
        config_dir_path = profile_dir

    return AutoCreateResult(
        opencode_config=opencode_config_path,
        tui_config=tui_config_path,
        config_dir=config_dir_path,
    )


def render_zsh_env(profile: ProfileConfig | None) -> str:
    lines = [
        "# This file is managed by agent-kit opencode-env-switch.",
    ]
    values = {
        "OPENCODE_CONFIG": profile.opencode_config if profile else None,
        "OPENCODE_TUI_CONFIG": profile.tui_config if profile else None,
        "OPENCODE_CONFIG_DIR": profile.config_dir if profile else None,
    }
    for env_name, path in values.items():
        if path is None:
            lines.append(f"unset {env_name}")
            continue
        lines.append(f"export {env_name}={_double_quote(str(path))}")
    return "\n".join(lines) + "\n"


def write_shell_source_file(source_file: Path, content: str) -> Path:
    source_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = source_file.with_suffix(source_file.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(source_file)
    return source_file


def install_or_update_zsh_integration(rc_file: Path, source_file: Path) -> None:
    current = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
    block = build_zsh_source_block(source_file)
    if ZSH_BLOCK_PATTERN.search(current):
        updated = ZSH_BLOCK_PATTERN.sub(block, current, count=1)
    else:
        separator = "\n" if current and not current.endswith("\n") else ""
        updated = f"{current}{separator}{block}"
    rc_file.parent.mkdir(parents=True, exist_ok=True)
    rc_file.write_text(updated, encoding="utf-8")


def build_zsh_source_block(source_file: Path) -> str:
    return (
        f"{ZSH_MARKER_BEGIN}\n"
        f"[[ -f {_double_quote(str(source_file))} ]] && source {_double_quote(str(source_file))}\n"
        f"{ZSH_MARKER_END}\n"
    )


def inspect_zsh_integration(zsh_config: ZshShellConfig) -> ZshIntegrationStatus:
    rc_exists = zsh_config.rc_file.exists()
    content = zsh_config.rc_file.read_text(encoding="utf-8") if rc_exists else ""
    return ZshIntegrationStatus(
        rc_exists=rc_exists,
        block_present=ZSH_MARKER_BEGIN in content and ZSH_MARKER_END in content,
        source_exists=zsh_config.source_file.exists(),
    )


def add_profile(
    config: OpencodeEnvSwitchConfig,
    profile: ProfileConfig,
) -> OpencodeEnvSwitchConfig:
    validate_user_profile_name_for_register(profile.name)
    _validate_profile_paths(profile)
    if any(existing.name == profile.name for existing in config.profiles):
        raise ValueError(f"duplicate profile name: {profile.name}")
    return replace(config, profiles=[*config.profiles, profile])


def update_profile(
    config: OpencodeEnvSwitchConfig,
    name: str,
    *,
    new_name: str | None = None,
    description: str | None = None,
    opencode_config: Path | None = None,
    tui_config: Path | None = None,
    config_dir: Path | None = None,
) -> OpencodeEnvSwitchConfig:
    current = get_profile(config, name)
    if new_name is not None:
        validate_user_profile_name_for_register(new_name)
    updated = ProfileConfig(
        name=new_name or current.name,
        description=description if description is not None else current.description,
        opencode_config=opencode_config if opencode_config is not None else current.opencode_config,
        tui_config=tui_config if tui_config is not None else current.tui_config,
        config_dir=config_dir if config_dir is not None else current.config_dir,
    )
    _validate_profile_paths(updated)
    if updated.name != name and any(existing.name == updated.name for existing in config.profiles):
        raise ValueError(f"duplicate profile name: {updated.name}")
    profiles = [updated if profile.name == name else profile for profile in config.profiles]
    active_profile = config.active_profile
    if active_profile == name:
        active_profile = updated.name
    return replace(config, active_profile=active_profile, profiles=profiles)


def remove_profile(config: OpencodeEnvSwitchConfig, name: str) -> OpencodeEnvSwitchConfig:
    if config.active_profile == name:
        raise ValueError(f"cannot remove active profile: {name}")
    get_profile(config, name)
    return replace(
        config,
        profiles=[profile for profile in config.profiles if profile.name != name],
    )


def activate_profile(config: OpencodeEnvSwitchConfig, name: str) -> OpencodeEnvSwitchConfig:
    if is_system_default_profile_name(name):
        return replace(config, active_profile=name)
    get_profile(config, name)
    return replace(config, active_profile=name)


def set_zsh_installed(config: OpencodeEnvSwitchConfig, installed: bool) -> OpencodeEnvSwitchConfig:
    return replace(
        config,
        shells=ShellsConfig(
            zsh=replace(config.shells.zsh, installed=installed)
        ),
    )


def get_profile(config: OpencodeEnvSwitchConfig, name: str) -> ProfileConfig:
    for profile in config.profiles:
        if profile.name == name:
            return profile
    raise ValueError(f"unknown profile: {name}")


def profile_path_statuses(profile: ProfileConfig) -> dict[str, OptionalPathStatus]:
    return {
        "opencode_config": _optional_path_status(
            "opencode_config",
            profile.opencode_config,
            expected_type="file",
        ),
        "tui_config": _optional_path_status(
            "tui_config",
            profile.tui_config,
            expected_type="file",
        ),
        "config_dir": _optional_path_status(
            "config_dir",
            profile.config_dir,
            expected_type="dir",
        ),
    }


def validate_profile_paths(profile: ProfileConfig) -> None:
    _validate_profile_paths(profile)


def _validate_profile_paths(profile: ProfileConfig) -> None:
    statuses = profile_path_statuses(profile)
    if all(status.path is None for status in statuses.values()):
        raise ValueError(f"profile must define at least one path: {profile.name}")
    for status in statuses.values():
        if status.error:
            raise ValueError(status.error)


def _optional_path_status(label: str, path: Path | None, *, expected_type: str) -> OptionalPathStatus:
    if path is None:
        return OptionalPathStatus(label=label, path=None, valid=None, error=None)
    if not path.exists():
        return OptionalPathStatus(
            label=label,
            path=path,
            valid=False,
            error=f"{label} does not exist: {path}",
        )
    if expected_type == "file" and not path.is_file():
        return OptionalPathStatus(
            label=label,
            path=path,
            valid=False,
            error=f"{label} is not a file: {path}",
        )
    if expected_type == "dir" and not path.is_dir():
        return OptionalPathStatus(
            label=label,
            path=path,
            valid=False,
            error=f"{label} is not a directory: {path}",
        )
    return OptionalPathStatus(label=label, path=path, valid=True, error=None)


def _double_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
