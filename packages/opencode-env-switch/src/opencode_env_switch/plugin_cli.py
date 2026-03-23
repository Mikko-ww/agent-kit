from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import questionary
import typer

from opencode_env_switch import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from opencode_env_switch.config import (
    OpencodeEnvSwitchConfig,
    ProfileConfig,
    default_config,
    load_config,
    save_config,
)
from opencode_env_switch.logic import (
    activate_profile,
    add_profile,
    get_profile,
    inspect_zsh_integration,
    install_or_update_zsh_integration,
    profile_path_statuses,
    remove_profile,
    render_zsh_env,
    set_zsh_installed,
    update_profile,
    validate_profile_paths,
    write_shell_source_file,
)


class InteractiveIO(Protocol):
    def echo(self, message: str) -> None: ...

    def warn(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def prompt_text(self, message: str, default: str | None = None) -> str: ...

    def confirm(self, message: str, default: bool = False) -> bool: ...

    def select_one(self, message: str, choices: Sequence[str]) -> str: ...


class QuestionaryIO:
    def echo(self, message: str) -> None:
        typer.echo(message)

    def warn(self, message: str) -> None:
        typer.echo(message)

    def error(self, message: str) -> None:
        typer.echo(message, err=True)

    def prompt_text(self, message: str, default: str | None = None) -> str:
        kwargs = {"default": default} if default is not None else {}
        answer = questionary.text(message, **kwargs).ask()
        if answer is None:
            raise typer.Abort()
        return answer

    def confirm(self, message: str, default: bool = False) -> bool:
        answer = questionary.confirm(message, default=default).ask()
        if answer is None:
            raise typer.Abort()
        return bool(answer)

    def select_one(self, message: str, choices: Sequence[str]) -> str:
        answer = questionary.select(
            message,
            choices=[questionary.Choice(title=choice, value=choice) for choice in choices],
        ).ask()
        if answer is None:
            raise typer.Abort()
        return str(answer)


@dataclass(slots=True)
class PluginRuntime:
    logger: logging.Logger
    cwd: Path
    config_root: Path
    data_root: Path
    cache_root: Path
    io: InteractiveIO
    default_zsh_rc_file: Path | None = None


def default_runtime_factory() -> PluginRuntime:
    return PluginRuntime(
        logger=logging.getLogger(f"agent-kit.{PLUGIN_ID}"),
        cwd=Path.cwd(),
        config_root=Path(os.environ.get("AGENT_KIT_CONFIG_DIR", "~/.config/agent-kit")).expanduser(),
        data_root=Path(os.environ.get("AGENT_KIT_DATA_DIR", "~/.local/share/agent-kit")).expanduser(),
        cache_root=Path(os.environ.get("AGENT_KIT_CACHE_DIR", "~/.cache/agent-kit")).expanduser(),
        io=QuestionaryIO(),
    )


def build_app(runtime_factory=default_runtime_factory) -> typer.Typer:
    app = typer.Typer(
        help="Switch OpenCode profiles through managed shell environment files.",
        no_args_is_help=True,
        add_completion=False,
    )
    init_app = typer.Typer(help="Install shell integration.", no_args_is_help=True)
    profile_app = typer.Typer(help="Manage OpenCode profiles.", no_args_is_help=True)
    app.add_typer(init_app, name="init")
    app.add_typer(profile_app, name="profile")

    @app.callback(invoke_without_command=True)
    def app_callback(
        ctx: typer.Context,
        plugin_metadata: bool = typer.Option(
            False,
            "--plugin-metadata",
            help="Print plugin metadata as JSON.",
            is_eager=True,
        ),
    ) -> None:
        if plugin_metadata:
            typer.echo(
                json.dumps(
                    {
                        "plugin_id": PLUGIN_ID,
                        "installed_version": __version__,
                        "api_version": API_VERSION,
                        "config_version": CONFIG_VERSION,
                    }
                )
            )
            raise typer.Exit()

    @init_app.command("zsh")
    def init_zsh_command() -> None:
        runtime = runtime_factory()
        config = _load_or_default_config(runtime)
        if not runtime.io.confirm(
            f"Install zsh integration into {config.shells.zsh.rc_file}?",
            default=True,
        ):
            runtime.io.warn("Skipped zsh integration.")
            return
        active_profile = _active_profile_or_none(config)
        write_shell_source_file(config.shells.zsh.source_file, render_zsh_env(active_profile))
        install_or_update_zsh_integration(config.shells.zsh.rc_file, config.shells.zsh.source_file)
        saved_path = save_config(runtime.config_root, set_zsh_installed(config, True))
        runtime.io.echo(f"Saved configuration to {saved_path}")
        runtime.io.echo(f"Installed zsh integration into {config.shells.zsh.rc_file}")

    @profile_app.command("list")
    def profile_list_command() -> None:
        runtime = runtime_factory()
        config = _load_or_default_config(runtime)
        if not config.profiles:
            runtime.io.warn("No profiles configured.")
            return
        runtime.io.echo(f"active_profile: {config.active_profile}")
        for profile in config.profiles:
            runtime.io.echo(f"[{profile.name}]")
            runtime.io.echo(f"description: {profile.description or '-'}")
            runtime.io.echo(f"opencode_config: {profile.opencode_config or '-'}")
            runtime.io.echo(f"tui_config: {profile.tui_config or '-'}")
            runtime.io.echo(f"config_dir: {profile.config_dir or '-'}")

    @profile_app.command("add")
    def profile_add_command(
        name: str | None = typer.Option(None, "--name", help="Profile name."),
        description: str | None = typer.Option(None, "--description", help="Profile description."),
        opencode_config: str | None = typer.Option(None, "--opencode-config", help="OpenCode config file path."),
        tui_config: str | None = typer.Option(None, "--tui-config", help="OpenCode TUI config file path."),
        config_dir: str | None = typer.Option(None, "--config-dir", help="OpenCode config directory path."),
    ) -> None:
        runtime = runtime_factory()
        config = _load_or_default_config(runtime)
        try:
            profile = ProfileConfig(
                name=_resolve_profile_name(runtime, name),
                description=description,
                opencode_config=_resolve_optional_file_path(opencode_config, key="opencode_config"),
                tui_config=_resolve_optional_file_path(tui_config, key="tui_config"),
                config_dir=_resolve_optional_dir_path(config_dir),
            )
            if all(path is None for path in (profile.opencode_config, profile.tui_config, profile.config_dir)):
                profile = ProfileConfig(
                    name=profile.name,
                    description=profile.description,
                    opencode_config=_prompt_optional_file_path(runtime, "OpenCode config file"),
                    tui_config=_prompt_optional_file_path(runtime, "OpenCode TUI config file"),
                    config_dir=_prompt_optional_dir_path(runtime, "OpenCode config directory"),
                )
            updated = add_profile(config, profile)
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"Saved configuration to {saved_path}")

    @profile_app.command("update")
    def profile_update_command(
        name: str | None = typer.Option(None, "--name", help="Existing profile name."),
        new_name: str | None = typer.Option(None, "--new-name", help="New profile name."),
        description: str | None = typer.Option(None, "--description", help="New profile description."),
        opencode_config: str | None = typer.Option(None, "--opencode-config", help="OpenCode config file path."),
        tui_config: str | None = typer.Option(None, "--tui-config", help="OpenCode TUI config file path."),
        config_dir: str | None = typer.Option(None, "--config-dir", help="OpenCode config directory path."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_profiles(runtime)
        selected_name = name or _select_profile_name(runtime, config)
        if (
            new_name is None
            and description is None
            and opencode_config is None
            and tui_config is None
            and config_dir is None
        ):
            existing = get_profile(config, selected_name)
            new_name = runtime.io.prompt_text("Profile name", default=existing.name).strip()
            description = runtime.io.prompt_text(
                "Profile description",
                default=existing.description or "",
            ).strip() or existing.description
            opencode_config = runtime.io.prompt_text(
                "OpenCode config file",
                default=str(existing.opencode_config) if existing.opencode_config else "",
            ).strip() or (str(existing.opencode_config) if existing.opencode_config else None)
            tui_config = runtime.io.prompt_text(
                "OpenCode TUI config file",
                default=str(existing.tui_config) if existing.tui_config else "",
            ).strip() or (str(existing.tui_config) if existing.tui_config else None)
            config_dir = runtime.io.prompt_text(
                "OpenCode config directory",
                default=str(existing.config_dir) if existing.config_dir else "",
            ).strip() or (str(existing.config_dir) if existing.config_dir else None)
        try:
            updated = update_profile(
                config,
                selected_name,
                new_name=new_name,
                description=description,
                opencode_config=_resolve_optional_file_path(opencode_config, key="opencode_config"),
                tui_config=_resolve_optional_file_path(tui_config, key="tui_config"),
                config_dir=_resolve_optional_dir_path(config_dir),
            )
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"Saved configuration to {saved_path}")

    @profile_app.command("remove")
    def profile_remove_command(
        name: str = typer.Option(..., "--name", help="Profile name."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_profiles(runtime)
        try:
            updated = remove_profile(config, name)
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"Saved configuration to {saved_path}")

    @app.command("switch")
    def switch_command(
        name: str | None = typer.Option(None, "--name", help="Profile name."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_profiles(runtime)
        selected_name = name or _select_profile_name(runtime, config)
        try:
            profile = get_profile(config, selected_name)
            validate_profile_paths(profile)
            write_shell_source_file(config.shells.zsh.source_file, render_zsh_env(profile))
            updated = activate_profile(config, selected_name)
            save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"Switched active profile to {selected_name}")

    @app.command("export")
    def export_command(
        name: str | None = typer.Option(None, "--name", help="Profile name."),
        shell: str = typer.Option("zsh", "--shell", help="Shell type."),
    ) -> None:
        runtime = runtime_factory()
        if shell != "zsh":
            _exit_with_error(runtime, ValueError(f"unsupported shell: {shell}"))
        config = _require_profiles(runtime)
        selected_name = name or _select_profile_name(runtime, config)
        try:
            profile = get_profile(config, selected_name)
            validate_profile_paths(profile)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(render_zsh_env(profile))

    @app.command("status")
    def status_command() -> None:
        runtime = runtime_factory()
        config_path = runtime.config_root / "plugins" / PLUGIN_ID / "config.jsonc"
        loaded = load_config(runtime.config_root)
        config = loaded or default_config(runtime.config_root)
        zsh_status = inspect_zsh_integration(config.shells.zsh)

        runtime.io.echo(f"config_path: {config_path}")
        runtime.io.echo(f"config_exists: {_format_yes_no(loaded is not None)}")
        runtime.io.echo(f"active_profile: {config.active_profile}")
        runtime.io.echo(f"profiles: {len(config.profiles)}")
        runtime.io.echo(f"zsh_rc_file: {config.shells.zsh.rc_file}")
        runtime.io.echo(f"zsh_source_file: {config.shells.zsh.source_file}")
        runtime.io.echo(f"zsh_config_installed: {_format_yes_no(config.shells.zsh.installed)}")
        runtime.io.echo(f"zsh_block_present: {_format_yes_no(zsh_status.block_present)}")
        runtime.io.echo(f"zsh_source_exists: {_format_yes_no(zsh_status.source_exists)}")

        for profile in config.profiles:
            runtime.io.echo(f"[{profile.name}]")
            runtime.io.echo(f"active: {_format_yes_no(profile.name == config.active_profile)}")
            runtime.io.echo(f"description: {profile.description or '-'}")
            statuses = profile_path_statuses(profile)
            for key, status in statuses.items():
                runtime.io.echo(f"{key}: {status.path or '-'}")
                runtime.io.echo(f"{key}_valid: {_format_optional_validity(status.valid)}")

    return app


def main() -> None:
    build_app()()


def _load_or_default_config(runtime: PluginRuntime) -> OpencodeEnvSwitchConfig:
    return load_config(runtime.config_root) or default_config(
        runtime.config_root,
        zsh_rc_file=runtime.default_zsh_rc_file,
    )


def _require_profiles(runtime: PluginRuntime) -> OpencodeEnvSwitchConfig:
    config = _load_or_default_config(runtime)
    if not config.profiles:
        _exit_with_error(runtime, ValueError("no profiles configured"))
    return config


def _select_profile_name(runtime: PluginRuntime, config: OpencodeEnvSwitchConfig) -> str:
    return runtime.io.select_one(
        "Select profile",
        [profile.name for profile in config.profiles],
    )


def _resolve_profile_name(runtime: PluginRuntime, name: str | None) -> str:
    resolved = name.strip() if name is not None else ""
    if resolved:
        return resolved
    while True:
        resolved = runtime.io.prompt_text("Profile name").strip()
        if resolved:
            return resolved
        runtime.io.error("profile name is required")


def _resolve_optional_file_path(value: str | None, *, key: str) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.exists():
        raise ValueError(f"{key} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{key} is not a file: {path}")
    return path


def _resolve_optional_dir_path(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.exists():
        raise ValueError(f"config_dir does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"config_dir is not a directory: {path}")
    return path


def _prompt_optional_file_path(runtime: PluginRuntime, label: str) -> Path | None:
    value = runtime.io.prompt_text(label, default="").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.exists():
        _exit_with_error(runtime, ValueError(f"{_label_to_key(label)} does not exist: {path}"))
    if not path.is_file():
        _exit_with_error(runtime, ValueError(f"{_label_to_key(label)} is not a file: {path}"))
    return path


def _prompt_optional_dir_path(runtime: PluginRuntime, label: str) -> Path | None:
    value = runtime.io.prompt_text(label, default="").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.exists():
        _exit_with_error(runtime, ValueError(f"{_label_to_key(label)} does not exist: {path}"))
    if not path.is_dir():
        _exit_with_error(runtime, ValueError(f"{_label_to_key(label)} is not a directory: {path}"))
    return path


def _active_profile_or_none(config: OpencodeEnvSwitchConfig) -> ProfileConfig | None:
    if config.active_profile is None:
        return None
    return get_profile(config, config.active_profile)


def _format_yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _format_optional_validity(value: bool | None) -> str:
    if value is None:
        return "-"
    return _format_yes_no(value)


def _label_to_key(label: str) -> str:
    normalized = label.strip().lower()
    if "tui" in normalized:
        return "tui_config"
    if "directory" in normalized:
        return "config_dir"
    return "opencode_config"


def _exit_with_error(runtime: PluginRuntime, exc: ValueError) -> None:
    runtime.io.error(str(exc))
    raise typer.Exit(code=1) from exc
