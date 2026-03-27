from __future__ import annotations

import json
import logging
import os
import shutil
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
from opencode_env_switch.locale import resolve_language
from opencode_env_switch.messages import translate
from opencode_env_switch.config import profiles_base_path
from opencode_env_switch.logic import (
    activate_profile,
    add_profile,
    create_profile_directory,
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
    language = _runtime_language(runtime_factory())
    app = typer.Typer(
        help=_t(language, "app.help"),
        no_args_is_help=True,
        add_completion=False,
    )
    init_app = typer.Typer(help=_t(language, "init.help"), no_args_is_help=True)
    profile_app = typer.Typer(help=_t(language, "profile.help"), no_args_is_help=True)
    wizard_app = typer.Typer(help=_t(language, "wizard.help"), no_args_is_help=True)
    app.add_typer(init_app, name="init")
    app.add_typer(profile_app, name="profile")
    app.add_typer(wizard_app, name="wizard")

    @app.callback(invoke_without_command=True)
    def app_callback(
        ctx: typer.Context,
        plugin_metadata: bool = typer.Option(
            False,
            "--plugin-metadata",
            help=_t(language, "metadata.help"),
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

    @init_app.command("zsh", help=_t(language, "init.zsh.help"))
    def init_zsh_command() -> None:
        runtime = runtime_factory()
        config = _load_or_default_config(runtime)
        if not runtime.io.confirm(
            _tr(runtime, "prompt.install_zsh", path=config.shells.zsh.rc_file),
            default=True,
        ):
            runtime.io.warn(_tr(runtime, "warning.skipped_zsh"))
            return
        active_profile = _active_profile_or_none(config)
        write_shell_source_file(config.shells.zsh.source_file, render_zsh_env(active_profile))
        install_or_update_zsh_integration(config.shells.zsh.rc_file, config.shells.zsh.source_file)
        saved_path = save_config(runtime.config_root, set_zsh_installed(config, True))
        runtime.io.echo(_tr(runtime, "saved.config", path=saved_path))
        runtime.io.echo(_tr(runtime, "result.installed_zsh", path=config.shells.zsh.rc_file))

    @profile_app.command("list", help=_t(language, "profile.list.help"))
    def profile_list_command() -> None:
        runtime = runtime_factory()
        config = _load_or_default_config(runtime)
        if not config.profiles:
            runtime.io.warn(_tr(runtime, "warning.no_profiles"))
            return
        runtime.io.echo(_tr(runtime, "label.active_profile", value=config.active_profile))
        for profile in config.profiles:
            runtime.io.echo(f"[{profile.name}]")
            runtime.io.echo(_tr(runtime, "label.description", value=profile.description or "-"))
            runtime.io.echo(_tr(runtime, "label.path_item", field="opencode_config", value=profile.opencode_config or "-"))
            runtime.io.echo(_tr(runtime, "label.path_item", field="tui_config", value=profile.tui_config or "-"))
            runtime.io.echo(_tr(runtime, "label.path_item", field="config_dir", value=profile.config_dir or "-"))

    @profile_app.command("add", help=_t(language, "profile.add.help"))
    def profile_add_command(
        name: str | None = typer.Option(None, "--name", help=_t(language, "option.name")),
        description: str | None = typer.Option(None, "--description", help=_t(language, "option.description")),
        opencode_config: str | None = typer.Option(None, "--opencode-config", help=_t(language, "option.opencode_config")),
        tui_config: str | None = typer.Option(None, "--tui-config", help=_t(language, "option.tui_config")),
        config_dir: str | None = typer.Option(None, "--config-dir", help=_t(language, "option.config_dir")),
        auto_create: bool = typer.Option(False, "--auto-create", help=_t(language, "option.auto_create")),
    ) -> None:
        runtime = runtime_factory()
        config = _load_or_default_config(runtime)
        created_dir: Path | None = None
        try:
            resolved_name = _resolve_profile_name(runtime, name)

            if auto_create:
                oc = _resolve_optional_file_path(opencode_config, key="opencode_config")
                tc = _resolve_optional_file_path(tui_config, key="tui_config")
                cd = _resolve_optional_dir_path(config_dir)
                result = create_profile_directory(
                    runtime.config_root,
                    resolved_name,
                    create_opencode_config=oc is None,
                    create_tui_config=tc is None,
                    create_config_dir=cd is None,
                )
                created_dir = profiles_base_path(runtime.config_root) / resolved_name
                runtime.io.echo(_tr(runtime, "result.auto_created_dir", path=created_dir))
                profile = ProfileConfig(
                    name=resolved_name,
                    description=description,
                    opencode_config=oc or result.opencode_config,
                    tui_config=tc or result.tui_config,
                    config_dir=cd or result.config_dir,
                )
            else:
                oc = _resolve_optional_file_path(opencode_config, key="opencode_config")
                tc = _resolve_optional_file_path(tui_config, key="tui_config")
                cd = _resolve_optional_dir_path(config_dir)
                if all(p is None for p in (oc, tc, cd)):
                    oc, tc, cd, created_dir = _prompt_path_actions(runtime, resolved_name)
                profile = ProfileConfig(
                    name=resolved_name,
                    description=description,
                    opencode_config=oc,
                    tui_config=tc,
                    config_dir=cd,
                )

            updated = add_profile(config, profile)
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            if created_dir and created_dir.exists():
                shutil.rmtree(created_dir)
            _exit_with_error(runtime, exc)
        runtime.io.echo(_tr(runtime, "saved.config", path=saved_path))

    @profile_app.command("update", help=_t(language, "profile.update.help"))
    def profile_update_command(
        name: str | None = typer.Option(None, "--name", help=_t(language, "option.existing_name")),
        new_name: str | None = typer.Option(None, "--new-name", help=_t(language, "option.new_name")),
        description: str | None = typer.Option(None, "--description", help=_t(language, "option.new_description")),
        opencode_config: str | None = typer.Option(None, "--opencode-config", help=_t(language, "option.opencode_config")),
        tui_config: str | None = typer.Option(None, "--tui-config", help=_t(language, "option.tui_config")),
        config_dir: str | None = typer.Option(None, "--config-dir", help=_t(language, "option.config_dir")),
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
            new_name = runtime.io.prompt_text(_tr(runtime, "prompt.profile_name"), default=existing.name).strip()
            description = runtime.io.prompt_text(
                _tr(runtime, "prompt.profile_description"),
                default=existing.description or "",
            ).strip() or existing.description
            opencode_config = runtime.io.prompt_text(
                _tr(runtime, "prompt.opencode_config"),
                default=str(existing.opencode_config) if existing.opencode_config else "",
            ).strip() or (str(existing.opencode_config) if existing.opencode_config else None)
            tui_config = runtime.io.prompt_text(
                _tr(runtime, "prompt.tui_config"),
                default=str(existing.tui_config) if existing.tui_config else "",
            ).strip() or (str(existing.tui_config) if existing.tui_config else None)
            config_dir = runtime.io.prompt_text(
                _tr(runtime, "prompt.config_dir"),
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
        runtime.io.echo(_tr(runtime, "saved.config", path=saved_path))

    @profile_app.command("remove", help=_t(language, "profile.remove.help"))
    def profile_remove_command(
        name: str = typer.Option(..., "--name", help=_t(language, "option.name")),
    ) -> None:
        runtime = runtime_factory()
        config = _require_profiles(runtime)
        try:
            updated = remove_profile(config, name)
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(_tr(runtime, "saved.config", path=saved_path))

    @app.command("switch", help=_t(language, "switch.help"))
    def switch_command(
        name: str | None = typer.Option(None, "--name", help=_t(language, "option.name")),
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
        runtime.io.echo(_tr(runtime, "result.switched", name=selected_name))

    @app.command("export", help=_t(language, "export.help"))
    def export_command(
        name: str | None = typer.Option(None, "--name", help=_t(language, "option.name")),
        shell: str = typer.Option("zsh", "--shell", help=_t(language, "option.shell")),
    ) -> None:
        runtime = runtime_factory()
        if shell != "zsh":
            _exit_with_error(runtime, ValueError(_tr(runtime, "error.unsupported_shell", shell=shell)))
        config = _require_profiles(runtime)
        selected_name = name or _select_profile_name(runtime, config)
        try:
            profile = get_profile(config, selected_name)
            validate_profile_paths(profile)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(render_zsh_env(profile))

    @app.command("status", help=_t(language, "status.help"))
    def status_command() -> None:
        runtime = runtime_factory()
        config_path = runtime.config_root / "plugins" / PLUGIN_ID / "config.jsonc"
        loaded = load_config(runtime.config_root)
        config = loaded or default_config(runtime.config_root)
        zsh_status = inspect_zsh_integration(config.shells.zsh)

        runtime.io.echo(_tr(runtime, "label.config_path", value=config_path))
        runtime.io.echo(_tr(runtime, "label.config_exists", value=_format_yes_no(loaded is not None, runtime)))
        runtime.io.echo(_tr(runtime, "label.active_profile", value=config.active_profile))
        runtime.io.echo(_tr(runtime, "label.profiles", value=len(config.profiles)))
        runtime.io.echo(_tr(runtime, "label.zsh_rc_file", value=config.shells.zsh.rc_file))
        runtime.io.echo(_tr(runtime, "label.zsh_source_file", value=config.shells.zsh.source_file))
        runtime.io.echo(_tr(runtime, "label.zsh_config_installed", value=_format_yes_no(config.shells.zsh.installed, runtime)))
        runtime.io.echo(_tr(runtime, "label.zsh_block_present", value=_format_yes_no(zsh_status.block_present, runtime)))
        runtime.io.echo(_tr(runtime, "label.zsh_source_exists", value=_format_yes_no(zsh_status.source_exists, runtime)))

        for profile in config.profiles:
            runtime.io.echo(f"[{profile.name}]")
            runtime.io.echo(_tr(runtime, "label.active", value=_format_yes_no(profile.name == config.active_profile, runtime)))
            runtime.io.echo(_tr(runtime, "label.description", value=profile.description or "-"))
            statuses = profile_path_statuses(profile)
            for key, status in statuses.items():
                runtime.io.echo(_tr(runtime, "label.path_item", field=key, value=status.path or "-"))
                runtime.io.echo(_tr(runtime, "label.path_validity", field=key, value=_format_optional_validity(status.valid, runtime)))

    @wizard_app.command("default", help=_t(language, "wizard.help"))
    def wizard_command() -> None:
        runtime = runtime_factory()
        runtime.io.echo(_tr(runtime, "wizard.welcome"))
        runtime.io.echo(_tr(runtime, "wizard.welcome_detail"))
        runtime.io.echo("")

        do_init_zsh = runtime.io.confirm(
            _tr(runtime, "wizard.prompt_init_zsh"),
            default=True,
        )

        do_create_profile = runtime.io.confirm(
            _tr(runtime, "wizard.prompt_create_profile"),
            default=True,
        )

        if not do_init_zsh and not do_create_profile:
            runtime.io.echo(_tr(runtime, "wizard.skip_all"))
            return

        config = default_config(runtime.config_root, zsh_rc_file=runtime.default_zsh_rc_file)

        if do_init_zsh:
            write_shell_source_file(config.shells.zsh.source_file, render_zsh_env(None))
            install_or_update_zsh_integration(config.shells.zsh.rc_file, config.shells.zsh.source_file)
            config = set_zsh_installed(config, True)
            runtime.io.echo(_tr(runtime, "result.installed_zsh", path=config.shells.zsh.rc_file))

        profile_name = None
        profile_description = None
        profile_opencode_config = None
        profile_tui_config = None
        profile_config_dir = None

        if do_create_profile:
            while True:
                name = runtime.io.prompt_text(_tr(runtime, "wizard.prompt_profile_name")).strip()
                if name:
                    profile_name = name
                    break
                runtime.io.error(_tr(runtime, "error.profile_name_required"))

            description = runtime.io.prompt_text(
                _tr(runtime, "wizard.prompt_profile_description"),
                default="",
            ).strip()
            profile_description = description or None

            auto_label = _tr(runtime, "prompt.path_mode.auto")
            manual_label = _tr(runtime, "prompt.path_mode.manual")
            path_mode = runtime.io.select_one(
                _tr(runtime, "prompt.path_mode"),
                [auto_label, manual_label],
            )

            if path_mode == auto_label:
                base = profiles_base_path(runtime.config_root) / profile_name
                runtime.io.echo(_tr(runtime, "wizard.auto_create_base_path", path=base))
                do_oc = runtime.io.confirm(_tr(runtime, "prompt.auto_create_opencode_config"), default=True)
                do_tc = runtime.io.confirm(_tr(runtime, "prompt.auto_create_tui_config"), default=True)
                do_cd = runtime.io.confirm(_tr(runtime, "prompt.auto_create_config_dir"), default=True)
                if do_oc or do_tc or do_cd:
                    result = create_profile_directory(
                        runtime.config_root,
                        profile_name,
                        create_opencode_config=do_oc,
                        create_tui_config=do_tc,
                        create_config_dir=do_cd,
                    )
                    runtime.io.echo(_tr(runtime, "result.auto_created_dir", path=base))
                    profile_opencode_config = result.opencode_config
                    profile_tui_config = result.tui_config
                    profile_config_dir = result.config_dir
            else:
                opencode_config_path = runtime.io.prompt_text(
                    _tr(runtime, "wizard.prompt_opencode_config"),
                    default="",
                ).strip()
                if opencode_config_path:
                    profile_opencode_config = _resolve_optional_file_path(opencode_config_path, key="opencode_config")

                tui_config_path = runtime.io.prompt_text(
                    _tr(runtime, "wizard.prompt_tui_config"),
                    default="",
                ).strip()
                if tui_config_path:
                    profile_tui_config = _resolve_optional_file_path(tui_config_path, key="tui_config")

                config_dir_path = runtime.io.prompt_text(
                    _tr(runtime, "wizard.prompt_config_dir"),
                    default="",
                ).strip()
                if config_dir_path:
                    profile_config_dir = _resolve_optional_dir_path(config_dir_path)

            runtime.io.echo("")
            runtime.io.echo(_tr(runtime, "wizard.confirm_summary"))
            runtime.io.echo(_tr(runtime, "wizard.confirm_profile_name", name=profile_name))
            runtime.io.echo(_tr(runtime, "wizard.confirm_profile_description", description=profile_description or "-"))
            runtime.io.echo(_tr(runtime, "wizard.confirm_opencode_config", path=str(profile_opencode_config) if profile_opencode_config else "-"))
            runtime.io.echo(_tr(runtime, "wizard.confirm_tui_config", path=str(profile_tui_config) if profile_tui_config else "-"))
            runtime.io.echo(_tr(runtime, "wizard.confirm_config_dir", path=str(profile_config_dir) if profile_config_dir else "-"))

            if not runtime.io.confirm(_tr(runtime, "wizard.confirm_save"), default=True):
                runtime.io.echo(_tr(runtime, "wizard.skip_all"))
                return

            profile = ProfileConfig(
                name=profile_name,
                description=profile_description,
                opencode_config=profile_opencode_config,
                tui_config=profile_tui_config,
                config_dir=profile_config_dir,
            )
            config = add_profile(config, profile)
            config = activate_profile(config, profile_name)

        saved_path = save_config(runtime.config_root, config)
        runtime.io.echo(_tr(runtime, "saved.config", path=saved_path))

        if profile_name:
            runtime.io.echo(_tr(runtime, "wizard.completed"))
            runtime.io.echo(_tr(runtime, "wizard.completed_detail", name=profile_name))
        else:
            runtime.io.echo(_tr(runtime, "wizard.completed"))

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
        _tr(runtime, "prompt.select_profile"),
        [profile.name for profile in config.profiles],
    )


def _resolve_profile_name(runtime: PluginRuntime, name: str | None) -> str:
    resolved = name.strip() if name is not None else ""
    if resolved:
        return resolved
    while True:
        resolved = runtime.io.prompt_text(_tr(runtime, "prompt.profile_name")).strip()
        if resolved:
            return resolved
        runtime.io.error(_tr(runtime, "error.profile_name_required"))


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


def _prompt_path_actions(
    runtime: PluginRuntime,
    profile_name: str,
) -> tuple[Path | None, Path | None, Path | None, Path | None]:
    auto_label = _tr(runtime, "prompt.path_action.auto")
    manual_label = _tr(runtime, "prompt.path_action.manual")
    skip_label = _tr(runtime, "prompt.path_action.skip")
    choices = [auto_label, manual_label, skip_label]

    auto_oc = False
    auto_tc = False
    auto_cd = False
    oc: Path | None = None
    tc: Path | None = None
    cd: Path | None = None

    action = runtime.io.select_one(
        _tr(runtime, "prompt.path_action", field="opencode_config"), choices,
    )
    if action == auto_label:
        auto_oc = True
    elif action == manual_label:
        oc = _prompt_optional_file_path(runtime, _tr(runtime, "prompt.opencode_config"))

    action = runtime.io.select_one(
        _tr(runtime, "prompt.path_action", field="tui_config"), choices,
    )
    if action == auto_label:
        auto_tc = True
    elif action == manual_label:
        tc = _prompt_optional_file_path(runtime, _tr(runtime, "prompt.tui_config"))

    action = runtime.io.select_one(
        _tr(runtime, "prompt.path_action", field="config_dir"), choices,
    )
    if action == auto_label:
        auto_cd = True
    elif action == manual_label:
        cd = _prompt_optional_dir_path(runtime, _tr(runtime, "prompt.config_dir"))

    created_dir: Path | None = None
    if auto_oc or auto_tc or auto_cd:
        result = create_profile_directory(
            runtime.config_root,
            profile_name,
            create_opencode_config=auto_oc,
            create_tui_config=auto_tc,
            create_config_dir=auto_cd,
        )
        created_dir = profiles_base_path(runtime.config_root) / profile_name
        runtime.io.echo(_tr(runtime, "result.auto_created_dir", path=created_dir))
        oc = oc or result.opencode_config
        tc = tc or result.tui_config
        cd = cd or result.config_dir

    return oc, tc, cd, created_dir


def _active_profile_or_none(config: OpencodeEnvSwitchConfig) -> ProfileConfig | None:
    if config.active_profile is None:
        return None
    return get_profile(config, config.active_profile)


def _format_yes_no(value: bool, runtime: PluginRuntime | None = None) -> str:
    return translate(_runtime_language(runtime), "yes" if value else "no")


def _format_optional_validity(value: bool | None, runtime: PluginRuntime | None = None) -> str:
    if value is None:
        return "-"
    return _format_yes_no(value, runtime)


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


def _runtime_language(runtime: PluginRuntime | None) -> str:
    if runtime is not None and hasattr(runtime, "language"):
        return getattr(runtime, "language")
    if runtime is not None:
        return resolve_language(runtime.config_root)
    return resolve_language(Path(os.environ.get("AGENT_KIT_CONFIG_DIR", "~/.config/agent-kit")).expanduser())


def _tr(runtime: PluginRuntime, key: str, **kwargs: object) -> str:
    return translate(_runtime_language(runtime), key, **kwargs)


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)
