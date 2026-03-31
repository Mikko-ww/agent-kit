from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import typer

from self_evolve import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from self_evolve.config import ProjectConfig, load_project_config, save_plugin_config, save_project_config
from self_evolve.locale import resolve_language
from self_evolve.logic import (
    capture_memory,
    get_memory,
    get_skill,
    get_status,
    init_agent_dir,
    is_initialized,
    list_memories,
    list_skills,
)
from self_evolve.messages import translate


@dataclass(slots=True)
class PluginRuntime:
    logger: logging.Logger
    cwd: Path
    config_root: Path
    data_root: Path
    cache_root: Path


def default_runtime_factory() -> PluginRuntime:
    return PluginRuntime(
        logger=logging.getLogger(f"agent-kit.{PLUGIN_ID}"),
        cwd=Path.cwd(),
        config_root=Path(os.environ.get("AGENT_KIT_CONFIG_DIR", "~/.config/agent-kit")).expanduser(),
        data_root=Path(os.environ.get("AGENT_KIT_DATA_DIR", "~/.local/share/agent-kit")).expanduser(),
        cache_root=Path(os.environ.get("AGENT_KIT_CACHE_DIR", "~/.cache/agent-kit")).expanduser(),
    )


def build_app(runtime_factory=default_runtime_factory) -> typer.Typer:
    language = _runtime_language(runtime_factory())
    app = typer.Typer(
        help=_t(language, "app.help"),
        no_args_is_help=True,
        add_completion=False,
    )
    skill_app = typer.Typer(help=_t(language, "skill.help"), no_args_is_help=True)
    app.add_typer(skill_app, name="skill")

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

    @app.command("init", help=_t(language, "init.help"))
    def init_command() -> None:
        runtime = runtime_factory()
        project_root = runtime.cwd
        if is_initialized(project_root):
            typer.echo(_tr(runtime, "warning.already_initialized"))
            return
        agent_dir = init_agent_dir(project_root)
        config = ProjectConfig(project_root=project_root)
        save_project_config(config)
        save_plugin_config(runtime.config_root, project_root)
        typer.echo(_tr(runtime, "init.success", path=agent_dir))

    @app.command("capture", help=_t(language, "capture.help"))
    def capture_command(
        category: str = typer.Option(..., "--category", help=_t(language, "option.category")),
        subject: str = typer.Option(..., "--subject", help=_t(language, "option.subject")),
        content: str = typer.Option(..., "--content", help=_t(language, "option.content")),
        source: str = typer.Option("", "--source", help=_t(language, "option.source")),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        try:
            memory = capture_memory(config, category=category, subject=subject, content=content, source=source)
        except ValueError as exc:
            _exit_with_error(str(exc))
        typer.echo(_tr(runtime, "capture.success", memory_id=memory.id, category=memory.category))

    @app.command("list", help=_t(language, "list.help"))
    def list_command(
        category: str | None = typer.Option(None, "--category", help=_t(language, "option.category")),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        if category is not None:
            from self_evolve.logic import validate_category

            try:
                validate_category(category)
            except ValueError as exc:
                _exit_with_error(str(exc))
        memories = list_memories(config, category=category)
        if not memories:
            typer.echo(_tr(runtime, "warning.no_memories"))
            return
        for memory in memories:
            typer.echo(f"{memory.id} [{memory.category}] {memory.subject}")

    @app.command("show", help=_t(language, "show.help"))
    def show_command(
        memory_id: str = typer.Argument(..., help=_t(language, "option.id")),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        memory = get_memory(config, memory_id)
        if memory is None:
            _exit_with_error(_tr(runtime, "error.memory_not_found", memory_id=memory_id))
        typer.echo(_tr(runtime, "label.id", value=memory.id))
        typer.echo(_tr(runtime, "label.category", value=memory.category))
        typer.echo(_tr(runtime, "label.subject", value=memory.subject))
        typer.echo(_tr(runtime, "label.content", value=memory.content))
        typer.echo(_tr(runtime, "label.source", value=memory.source))
        typer.echo(_tr(runtime, "label.created_at", value=memory.created_at))

    @app.command("status", help=_t(language, "status.help"))
    def status_command() -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        summary = get_status(config)
        typer.echo(_tr(runtime, "label.project_root", value=summary.project_root))
        typer.echo(_tr(runtime, "label.memories", value=summary.total_memories))
        typer.echo(_tr(runtime, "label.rules", value=summary.rules))
        typer.echo(_tr(runtime, "label.patterns", value=summary.patterns))
        typer.echo(_tr(runtime, "label.learnings", value=summary.learnings))
        typer.echo(_tr(runtime, "label.skills", value=summary.skills))

    @skill_app.command("list", help=_t(language, "skill.list.help"))
    def skill_list_command() -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        skills = list_skills(config)
        if not skills:
            typer.echo(_tr(runtime, "warning.no_skills"))
            return
        for skill in skills:
            typer.echo(f"{skill.name}: {skill.description}")

    @skill_app.command("show", help=_t(language, "skill.show.help"))
    def skill_show_command(
        name: str = typer.Argument(..., help=_t(language, "option.skill_name")),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        skill = get_skill(config, name)
        if skill is None:
            _exit_with_error(_tr(runtime, "error.skill_not_found", name=name))
        typer.echo(_tr(runtime, "label.skill_name", value=skill.name))
        typer.echo(_tr(runtime, "label.skill_path", value=skill.path))
        typer.echo(_tr(runtime, "label.skill_description", value=skill.description))

    return app


def main() -> None:
    build_app()()


def _require_config(runtime: PluginRuntime) -> ProjectConfig:
    config = load_project_config(runtime.cwd)
    if config is None:
        typer.echo(_tr(runtime, "warning.not_initialized"))
        raise typer.Exit(code=1)
    return config


def _exit_with_error(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


def _runtime_language(runtime: PluginRuntime) -> str:
    return resolve_language(runtime.config_root)


def _tr(runtime: PluginRuntime, key: str, **kwargs: object) -> str:
    return translate(_runtime_language(runtime), key, **kwargs)


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)
