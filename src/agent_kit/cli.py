from __future__ import annotations

import typer
from typer import Context
from agent_kit.locale import SUPPORTED_LANGUAGES, load_config_language, resolve_language, save_config_language
from agent_kit.messages import translate
from agent_kit.plugin_manager import PluginError, PluginManager
from agent_kit.paths import AgentKitLayout


def create_app(
    *,
    manager_factory=PluginManager.from_defaults,
) -> typer.Typer:
    layout = AgentKitLayout.from_environment()
    language = resolve_language(config_path=layout.global_config_path).code
    manager = manager_factory()
    app = typer.Typer(
        help=_t(language, "app.help"),
        no_args_is_help=True,
        add_completion=False,
        epilog=_build_epilog(manager, language),
    )

    plugins_app = typer.Typer(help=_t(language, "plugins.help"), no_args_is_help=True, add_completion=False)
    config_app = typer.Typer(help=_t(language, "config.help"), no_args_is_help=True, add_completion=False)

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

    app.add_typer(plugins_app, name="plugins")
    app.add_typer(config_app, name="config")

    for plugin in manager.runnable_plugins():
        app.command(
            plugin.plugin_id,
            help=_plugin_help(language, plugin.plugin_id, plugin.description),
            context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        )(_build_plugin_command(manager, plugin.plugin_id))

    return app


def main() -> None:
    try:
        create_app()()
    except PluginError as exc:
        layout = AgentKitLayout.from_environment()
        language = resolve_language(config_path=layout.global_config_path).code
        typer.secho(_t(language, "plugin.error", message=str(exc)), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


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


def _plugin_help(language: str, plugin_id: str, fallback: str) -> str:
    key = f"plugins.dynamic.{plugin_id}"
    translated = _t(language, key, plugin_id=plugin_id)
    if translated == key:
        if language == "en":
            return fallback
        return _t(language, "plugins.dynamic.fallback", plugin_id=plugin_id)
    return translated


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)


def _display(value: object | None) -> object:
    return value if value is not None else "-"
