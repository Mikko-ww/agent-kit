from __future__ import annotations

import typer
from typer import Context
from agent_kit import __version__
from agent_kit.alias import disable_alias, enable_alias, get_alias_status
from agent_kit.locale import SUPPORTED_LANGUAGES, load_config_language, resolve_language, save_config_language
from agent_kit.messages import translate
from agent_kit.completion import (
    generate_zsh_completion_script,
    install_zsh_completion,
    remove_zsh_completion,
)
from agent_kit.plugin_manager import PluginError, PluginManager
from agent_kit.paths import AgentKitLayout

PLUGIN_COMMAND_ALIASES = {
    "opencode-env-switch": "oes",
    "self-evolve": "se",
    "skills-link": "sl",
}
RESERVED_COMMAND_NAMES = frozenset({"plugins", "config", "alias", "completion"})
GLOBAL_CONFIG_KEYS = {
    "language": {
        "values": ", ".join(SUPPORTED_LANGUAGES),
    },
}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"agent-kit {__version__}")
        raise typer.Exit()


def create_app(
    *,
    manager_factory=PluginManager.from_defaults,
) -> typer.Typer:
    layout = AgentKitLayout.from_environment()
    language = resolve_language(config_path=layout.global_config_path).code
    manager = manager_factory()
    runnable_plugins = manager.runnable_plugins()
    plugin_aliases = _build_plugin_alias_map(runnable_plugins)
    app = typer.Typer(
        help=_t(language, "app.help"),
        no_args_is_help=True,
        epilog=_build_epilog(manager, language),
    )

    @app.callback(invoke_without_command=True)
    def _root_callback(
        ctx: Context,
        version: bool = typer.Option(
            False,
            "--version",
            "-V",
            help=_t(language, "app.version.help"),
            callback=_version_callback,
            is_eager=True,
        ),
    ) -> None:
        return

    # 隐藏 Typer 默认注入的 --install-completion 和 --show-completion，
    # 由自定义 completion 子命令组代替。Click 底层的 _AGENT_KIT_COMPLETE
    # 环境变量补全机制不受影响。
    app._add_completion = False

    plugins_app = typer.Typer(help=_t(language, "plugins.help"), no_args_is_help=True)
    config_app = typer.Typer(help=_t(language, "config.help"), no_args_is_help=True)
    alias_app = typer.Typer(help=_t(language, "alias.help"), no_args_is_help=True)

    @plugins_app.command("refresh", help=_t(language, "plugins.refresh.help"))
    def refresh_command() -> None:
        registry = manager.refresh_registry()
        if not registry:
            typer.echo(_t(language, "plugins.refresh.empty"))
            return
        for plugin_id, entry in sorted(registry.items()):
            typer.echo(f"{plugin_id}: {entry.version}")

    @plugins_app.command("list", help=_t(language, "plugins.list.help"))
    def list_command() -> None:
        for plugin in manager.list_plugins():
            typer.echo(
                f"{plugin.plugin_id}: status={plugin.status} "
                f"installed={plugin.installed_version or '-'} "
                f"available={plugin.available_version or '-'}"
            )

    @plugins_app.command("info", help=_t(language, "plugins.info.help"))
    def info_command(plugin_id: str) -> None:
        info = manager.get_plugin_info(plugin_id)
        typer.echo(_t(language, "plugin.info.plugin_id", value=info.plugin_id))
        typer.echo(_t(language, "plugin.info.status", value=info.status))
        typer.echo(_t(language, "plugin.info.description", value=info.description))
        typer.echo(_t(language, "plugin.info.source_type", value=info.source_type))
        typer.echo(_t(language, "plugin.info.available_version", value=_display(info.available_version)))
        typer.echo(_t(language, "plugin.info.installed_version", value=_display(info.installed_version)))
        typer.echo(_t(language, "plugin.info.tag", value=_display(info.tag)))
        typer.echo(_t(language, "plugin.info.commit", value=_display(info.commit)))
        typer.echo(_t(language, "plugin.info.config_path", value=info.config_path))
        typer.echo(_t(language, "plugin.info.venv_path", value=info.venv_path))

    @plugins_app.command("install", help=_t(language, "plugins.install.help"))
    def install_command(plugin_id: str) -> None:
        record = manager.install_plugin(plugin_id)
        typer.echo(_t(language, "plugins.install.success", plugin_id=record.plugin_id, version=record.installed_version))

    @plugins_app.command("update", help=_t(language, "plugins.update.help"))
    def update_command(plugin_id: str) -> None:
        record = manager.update_plugin(plugin_id)
        typer.echo(_t(language, "plugins.update.success", plugin_id=record.plugin_id, version=record.installed_version))

    @plugins_app.command("remove", help=_t(language, "plugins.remove.help"))
    def remove_command(
        plugin_id: str,
        purge_config: bool = typer.Option(False, "--purge-config", help=_t(language, "plugins.remove.purge_config.help")),
    ) -> None:
        manager.remove_plugin(plugin_id, purge_config=purge_config)
        typer.echo(_t(language, "plugins.remove.success", plugin_id=plugin_id))

    @config_app.command("get", help=_t(language, "config.get.help"))
    def config_get_command(
        key: str = typer.Argument(..., help=_t(language, "config.key.help")),
    ) -> None:
        if key != "language":
            typer.secho(_t(language, "config.key.unsupported", key=key), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        typer.echo(_t(language, "config.language.value", value=load_config_language(layout.global_config_path) or "auto"))

    @config_app.command("list", help=_t(language, "config.list.help"))
    def config_list_command() -> None:
        for key, meta in GLOBAL_CONFIG_KEYS.items():
            typer.echo(_t(language, "config.list.item", name=key, values=meta["values"]))

    @config_app.command("set", help=_t(language, "config.set.help"))
    def config_set_command(
        key: str = typer.Argument(..., help=_t(language, "config.key.help")),
        value: str = typer.Argument(..., help=_t(language, "config.set.language.arg.help")),
    ) -> None:
        if key != "language":
            typer.secho(_t(language, "config.key.unsupported", key=key), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        if value not in SUPPORTED_LANGUAGES:
            typer.secho(_t("en", "config.language.invalid", value=value), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        save_config_language(layout.global_config_path, value)
        if value == "auto":
            typer.echo(_t(language, "config.language.reset"))
            return
        typer.echo(_t(language, "config.language.saved", value=value))

    @alias_app.command("enable", help=_t(language, "alias.enable.help"))
    def alias_enable_command() -> None:
        alias_path = layout.alias_wrapper_path("ak")
        try:
            result = enable_alias(alias_path)
        except ValueError:
            typer.secho(_t(language, "alias.error.unmanaged", path=alias_path), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        key = "alias.enable.created" if result.changed else "alias.enable.exists"
        typer.echo(_t(language, key, alias_name=result.alias_name, path=result.path))

    @alias_app.command("disable", help=_t(language, "alias.disable.help"))
    def alias_disable_command() -> None:
        alias_path = layout.alias_wrapper_path("ak")
        try:
            result = disable_alias(alias_path)
        except ValueError:
            typer.secho(_t(language, "alias.error.unmanaged", path=alias_path), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        key = "alias.disable.removed" if result.changed else "alias.disable.missing"
        typer.echo(_t(language, key, alias_name=result.alias_name, path=result.path))

    @alias_app.command("status", help=_t(language, "alias.status.help"))
    def alias_status_command() -> None:
        status = get_alias_status(layout.alias_wrapper_path("ak"))
        typer.echo(_t(language, "alias.status.value", value=status.state))
        typer.echo(_t(language, "alias.status.path", value=status.path))
        typer.echo(_t(language, "alias.status.bin_dir", value=status.bin_dir))
        path_key = "alias.status.path.ready" if status.path_in_path else "alias.status.path.missing"
        typer.echo(_t(language, path_key, value=status.bin_dir))

    completion_app = typer.Typer(help=_t(language, "completion.help"), no_args_is_help=True)

    @completion_app.command("install", help=_t(language, "completion.install.help"))
    def completion_install_command(
        shell: str = typer.Option("zsh", "--shell", "-s", help="Shell type"),
    ) -> None:
        if shell != "zsh":
            typer.secho(
                _t(language, "completion.shell.unsupported", shell=shell),
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(code=1)
        result = install_zsh_completion()
        key = f"completion.install.{result.method}"
        typer.echo(_t(language, key, path=result.path))

    @completion_app.command("show", help=_t(language, "completion.show.help"))
    def completion_show_command(
        shell: str = typer.Option("zsh", "--shell", "-s", help="Shell type"),
    ) -> None:
        if shell != "zsh":
            typer.secho(
                _t(language, "completion.shell.unsupported", shell=shell),
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(code=1)
        typer.echo(generate_zsh_completion_script())

    @completion_app.command("remove", help=_t(language, "completion.remove.help"))
    def completion_remove_command(
        shell: str = typer.Option("zsh", "--shell", "-s", help="Shell type"),
    ) -> None:
        if shell != "zsh":
            typer.secho(
                _t(language, "completion.shell.unsupported", shell=shell),
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(code=1)
        result = remove_zsh_completion()
        if result.removed:
            typer.echo(_t(language, "completion.remove.done", path=result.path))
        else:
            typer.echo(_t(language, "completion.remove.not_found"))

    app.add_typer(plugins_app, name="plugins")
    app.add_typer(config_app, name="config")
    app.add_typer(alias_app, name="alias")
    app.add_typer(completion_app, name="completion")

    for plugin in runnable_plugins:
        plugin_alias = plugin_aliases.get(plugin.plugin_id)
        app.command(
            plugin.plugin_id,
            help=_plugin_help(language, plugin.plugin_id, plugin.description, alias=plugin_alias),
            context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
            add_help_option=False,
        )(_build_plugin_command(manager, plugin.plugin_id))
        if plugin_alias is not None:
            app.command(
                plugin_alias,
                help=f"Alias for {plugin.plugin_id}",
                hidden=True,
                context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
                add_help_option=False,
            )(_build_plugin_command(manager, plugin.plugin_id))

    return app


def main() -> int:
    try:
        create_app()()
    except PluginError as exc:
        layout = AgentKitLayout.from_environment()
        language = resolve_language(config_path=layout.global_config_path).code
        typer.secho(_t(language, "plugin.error", message=str(exc)), fg=typer.colors.RED, err=True)
        return 1
    return 0


def _build_plugin_command(manager: PluginManager, plugin_id: str):
    def plugin_command(ctx: Context) -> None:
        result = manager.run_plugin(plugin_id, list(ctx.args))
        if getattr(result, "stdout", ""):
            typer.echo(result.stdout, nl=False)
        if getattr(result, "stderr", ""):
            typer.echo(result.stderr, err=True, nl=False)
        if getattr(result, "returncode", 0):
            raise typer.Exit(code=result.returncode)

    return plugin_command


def _build_epilog(manager: PluginManager, language: str) -> str | None:
    broken = manager.broken_plugins()
    if not broken:
        return None
    lines = [_t(language, "plugins.epilog.title")]
    for plugin in broken:
        lines.append(_t(language, "plugins.epilog.item", plugin_id=plugin.plugin_id, reason=plugin.reason))
    return "\n".join(lines)


def _plugin_help(language: str, plugin_id: str, fallback: str, *, alias: str | None = None) -> str:
    key = f"plugins.dynamic.{plugin_id}"
    translated = _t(language, key, plugin_id=plugin_id)
    if translated == key:
        if language == "en":
            help_text = fallback
        else:
            help_text = _t(language, "plugins.dynamic.fallback", plugin_id=plugin_id)
    else:
        help_text = translated
    if alias is None:
        return help_text
    return help_text + _t(language, "plugins.dynamic.alias_suffix", alias=alias)


def _build_plugin_alias_map(plugins: list[object]) -> dict[str, str]:
    plugin_ids = [str(plugin.plugin_id) for plugin in plugins]
    alias_owners: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for plugin_id in plugin_ids:
        alias = PLUGIN_COMMAND_ALIASES.get(plugin_id)
        if alias is None:
            continue
        if alias in RESERVED_COMMAND_NAMES:
            raise ValueError(f"plugin alias conflict: {plugin_id} alias {alias} conflicts with core command")
        if alias in plugin_ids:
            raise ValueError(f"plugin alias conflict: {plugin_id} alias {alias} conflicts with plugin_id {alias}")
        owner = alias_owners.get(alias)
        if owner is not None:
            raise ValueError(f"plugin alias conflict: {plugin_id} alias {alias} already used by {owner}")
        alias_owners[alias] = plugin_id
        aliases[plugin_id] = alias
    return aliases


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)


def _display(value: object | None) -> object:
    return value if value is not None else "-"
