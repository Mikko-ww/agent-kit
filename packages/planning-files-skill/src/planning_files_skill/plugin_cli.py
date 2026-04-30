from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import typer

from planning_files_skill import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from planning_files_skill.locale import normalize_language, resolve_language
from planning_files_skill.logic import (
    ImportRequest,
    PlanningFilesError,
    import_platform,
    inspect_platform,
    target_skill_dir,
)
from planning_files_skill.messages import translate


@dataclass(slots=True)
class PluginRuntime:
    logger: logging.Logger
    cwd: Path
    config_root: Path
    data_root: Path
    cache_root: Path
    home_dir: Path


def default_runtime_factory() -> PluginRuntime:
    return PluginRuntime(
        logger=logging.getLogger(PLUGIN_ID),
        cwd=Path.cwd(),
        config_root=Path(os.environ.get("AGENT_KIT_CONFIG_DIR", "~/.config/agent-kit")).expanduser(),
        data_root=Path(os.environ.get("AGENT_KIT_DATA_DIR", "~/.local/share/agent-kit")).expanduser(),
        cache_root=Path(os.environ.get("AGENT_KIT_CACHE_DIR", "~/.cache/agent-kit")).expanduser(),
        home_dir=Path.home(),
    )


def build_app(runtime_factory=default_runtime_factory) -> typer.Typer:
    runtime = runtime_factory()
    language = resolve_language(runtime.config_root)
    app = typer.Typer(help=_t(language, "app.help"), no_args_is_help=True, add_completion=False)

    @app.callback(invoke_without_command=True)
    def app_callback(
        plugin_metadata: bool = typer.Option(False, "--plugin-metadata", help=_t(language, "metadata.help"), is_eager=True),
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

    @app.command("import", help=_t(language, "import.help"))
    def import_command(
        platform: str = typer.Option(..., "--platform", help=_t(language, "option.platform")),
        requested_language: str | None = typer.Option(None, "--language", help=_t(language, "option.language")),
        scope: str = typer.Option("project", "--scope", help=_t(language, "option.scope")),
        dry_run: bool = typer.Option(False, "--dry-run", help=_t(language, "option.dry_run")),
        force: bool = typer.Option(False, "--force", help=_t(language, "option.force")),
    ) -> None:
        runtime = runtime_factory()
        try:
            lang = _resolve_template_language(runtime, requested_language)
            result = import_platform(
                ImportRequest(
                    platform=platform,
                    language=lang,
                    scope=scope,
                    project_root=runtime.cwd,
                    home_dir=runtime.home_dir,
                    dry_run=dry_run,
                    force=force,
                )
            )
        except PlanningFilesError as exc:
            typer.echo(_tr(runtime, "error", message=str(exc)), err=True)
            raise typer.Exit(code=1)

        display_path = target_skill_dir("generic" if platform == "all" else platform, scope, runtime.cwd, runtime.home_dir)
        typer.echo(_tr(runtime, "import.header", platform=platform, scope=scope, path=display_path))
        for action in result.actions:
            typer.echo(_tr(runtime, "action.line", action=action.action, path=action.path))
        for warning in result.warnings:
            if warning == "codex_hooks":
                typer.echo(_tr(runtime, "warning.codex_hooks"))

    @app.command("status", help=_t(language, "status.help"))
    def status_command(
        platform: str = typer.Option(..., "--platform", help=_t(language, "option.platform")),
        scope: str = typer.Option("project", "--scope", help=_t(language, "option.scope")),
    ) -> None:
        runtime = runtime_factory()
        try:
            platforms = ("codex", "cursor", "opencode", "generic") if platform == "all" else (platform,)
            for item in platforms:
                status = inspect_platform(platform=item, scope=scope, project_root=runtime.cwd, home_dir=runtime.home_dir)
                if status.installed:
                    typer.echo(
                        _tr(
                            runtime,
                            "status.installed",
                            platform=item,
                            scope=scope,
                            language=status.language or "-",
                            path=status.skill_path,
                        )
                    )
                else:
                    typer.echo(_tr(runtime, "status.missing", platform=item, scope=scope, path=status.skill_path))
        except PlanningFilesError as exc:
            typer.echo(_tr(runtime, "error", message=str(exc)), err=True)
            raise typer.Exit(code=1)

    return app


def main() -> None:
    build_app()()


def _resolve_template_language(runtime: PluginRuntime, requested: str | None) -> str:
    if requested is not None:
        normalized = normalize_language(requested)
        if normalized is None:
            raise PlanningFilesError(f"unsupported language: {requested}")
        return normalized
    return resolve_language(runtime.config_root)


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)


def _tr(runtime: PluginRuntime, key: str, **kwargs: object) -> str:
    return translate(resolve_language(runtime.config_root), key, **kwargs)
