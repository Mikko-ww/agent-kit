from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import questionary
import typer

from self_evolve import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from self_evolve.config import (
    SelfEvolveConfig,
    find_project_root,
    load_config,
)
from self_evolve.locale import resolve_language
from self_evolve.logic import (
    AnalysisResult,
    EvolutionStatus,
    EvolveResult,
    analyze_patterns,
    capture_learning,
    check_promotion_eligibility,
    evolve,
    filter_learnings,
    get_evolution_status,
    init_project,
    promote_learning,
    sync_rules,
)
from self_evolve.messages import translate
from self_evolve.storage import load_learning


class InteractiveIO(Protocol):
    def echo(self, message: str) -> None: ...

    def warn(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def prompt_text(self, message: str, default: str | None = None) -> str: ...

    def confirm(self, message: str, default: bool = False) -> bool: ...

    def select_one(self, message: str, choices: Sequence[str]) -> str: ...

    def select_many(self, message: str, choices: Sequence[str]) -> list[str]: ...


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

    def select_many(self, message: str, choices: Sequence[str]) -> list[str]:
        answer = questionary.checkbox(
            message,
            choices=[questionary.Choice(title=choice, value=choice) for choice in choices],
        ).ask()
        if answer is None:
            raise typer.Abort()
        return list(answer)


@dataclass(slots=True)
class PluginRuntime:
    logger: logging.Logger
    cwd: Path
    config_root: Path
    data_root: Path
    cache_root: Path
    io: InteractiveIO


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

        existing = find_project_root(project_root)
        if existing is not None and load_config(existing) is not None:
            runtime.io.warn(_tr(runtime, "warning.already_initialized", path=str(existing)))
            return

        runtime.io.echo(_tr(runtime, "init.welcome"))

        threshold = runtime.io.prompt_text(
            _tr(runtime, "prompt.promotion_threshold"),
            default="3",
        )
        min_tasks = runtime.io.prompt_text(
            _tr(runtime, "prompt.min_task_count"),
            default="2",
        )

        config = SelfEvolveConfig(
            promotion_threshold=int(threshold),
            min_task_count=int(min_tasks),
        )
        init_project(project_root, config)
        runtime.io.echo(_tr(runtime, "init.completed"))

    @app.command("capture", help=_t(language, "capture.help"))
    def capture_command(
        summary: str = typer.Option(..., "--summary", "-s", help=_t(language, "option.summary")),
        domain: str = typer.Option(..., "--domain", "-d", help=_t(language, "option.domain")),
        priority: str = typer.Option("medium", "--priority", "-p", help=_t(language, "option.priority")),
        detail: str = typer.Option("", "--detail", help=_t(language, "option.detail")),
        action: str = typer.Option("", "--action", help=_t(language, "option.action")),
        pattern_key: str = typer.Option("", "--pattern-key", help=_t(language, "option.pattern_key")),
        task_id: str = typer.Option("", "--task-id", help=_t(language, "option.task_id")),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        if project_root is None:
            return

        entry = capture_learning(
            project_root,
            summary=summary,
            domain=domain,
            priority=priority,
            detail=detail,
            suggested_action=action,
            pattern_key=pattern_key,
            task_id=task_id,
        )
        runtime.io.echo(_tr(runtime, "saved.learning", id=entry.id))

    @app.command("list", help=_t(language, "list.help"))
    def list_command(
        status: str | None = typer.Option(None, "--status", help=_t(language, "option.filter_status")),
        domain: str | None = typer.Option(None, "--domain", help=_t(language, "option.filter_domain")),
        priority: str | None = typer.Option(None, "--priority", help=_t(language, "option.filter_priority")),
        limit: int = typer.Option(20, "--limit", help=_t(language, "option.limit")),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        if project_root is None:
            return

        entries = filter_learnings(
            project_root,
            status=status,
            domain=domain,
            priority=priority,
            limit=limit,
        )

        if not entries:
            runtime.io.warn(_tr(runtime, "warning.no_learnings"))
            return

        for entry in entries:
            _print_entry(runtime, entry)

    @app.command("analyze", help=_t(language, "analyze.help"))
    def analyze_command() -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        if project_root is None:
            return

        config = load_config(project_root)
        if config is None:
            runtime.io.warn(_tr(runtime, "warning.not_initialized"))
            return

        result = analyze_patterns(project_root, config)
        _print_analysis(runtime, result)

    @app.command("promote", help=_t(language, "promote.help"))
    def promote_command(
        learning_id: str = typer.Argument(help=_t(language, "option.learning_id")),
        rule: str | None = typer.Option(None, "--rule", help=_t(language, "option.rule")),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        if project_root is None:
            return

        config = load_config(project_root)
        if config is None:
            runtime.io.warn(_tr(runtime, "warning.not_initialized"))
            return

        entry = load_learning(project_root, learning_id)
        if entry is None:
            runtime.io.warn(_tr(runtime, "warning.learning_not_found", id=learning_id))
            return

        if not check_promotion_eligibility(entry, config):
            runtime.io.warn(_tr(runtime, "warning.not_eligible", id=learning_id))
            return

        if rule is None:
            rule = runtime.io.prompt_text(_tr(runtime, "prompt.rule_text"))

        promoted = promote_learning(project_root, learning_id, rule)
        if promoted:
            runtime.io.echo(_tr(runtime, "saved.rule", id=promoted.id))

    @app.command("sync", help=_t(language, "sync.help"))
    def sync_command() -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        if project_root is None:
            return

        config = load_config(project_root)
        if config is None:
            runtime.io.warn(_tr(runtime, "warning.not_initialized"))
            return

        result = sync_rules(project_root, config)
        if result.rules_count == 0:
            runtime.io.echo(_tr(runtime, "sync.no_rules"))
            return

        runtime.io.echo(_tr(runtime, "sync.completed", count=result.rules_count, path=str(result.path)))

    @app.command("evolve", help=_t(language, "evolve.help"))
    def evolve_command() -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        if project_root is None:
            return

        config = load_config(project_root)
        if config is None:
            runtime.io.warn(_tr(runtime, "warning.not_initialized"))
            return

        runtime.io.echo(_tr(runtime, "evolve.start"))

        result = evolve(project_root, config)

        _print_analysis(runtime, result.analysis)

        if result.promoted:
            runtime.io.echo(_tr(runtime, "evolve.promoted", count=len(result.promoted)))
            for rule in result.promoted:
                runtime.io.echo(_tr(runtime, "saved.rule", id=rule.id))
        else:
            runtime.io.echo(_tr(runtime, "evolve.no_changes"))

        if result.sync_result:
            runtime.io.echo(
                _tr(runtime, "sync.completed", count=result.sync_result.rules_count, path=str(result.sync_result.path))
            )

        runtime.io.echo(_tr(runtime, "evolve.completed"))

    @app.command("status", help=_t(language, "status.help"))
    def status_command() -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        if project_root is None:
            return

        config = load_config(project_root)
        evo_status = get_evolution_status(project_root)
        _print_status(runtime, evo_status, config)

    return app


def main() -> None:
    build_app()()


def _runtime_language(runtime: PluginRuntime) -> str:
    return resolve_language(runtime.config_root)


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)


def _tr(runtime: PluginRuntime, key: str, **kwargs: object) -> str:
    return translate(_runtime_language(runtime), key, **kwargs)


def _require_project(runtime: PluginRuntime) -> Path | None:
    """查找项目根目录。如果未初始化，打印警告并返回 None。"""
    project_root = find_project_root(runtime.cwd)
    if project_root is None:
        runtime.io.warn(_tr(runtime, "warning.not_initialized"))
        return None

    config = load_config(project_root)
    if config is None:
        # 找到了项目根目录（有 .git）但未初始化 self-evolve
        runtime.io.warn(_tr(runtime, "warning.not_initialized"))
        return None

    return project_root


def _print_entry(runtime: PluginRuntime, entry) -> None:
    runtime.io.echo(_tr(runtime, "label.id", value=entry.id))
    runtime.io.echo(_tr(runtime, "label.summary", value=entry.summary))
    runtime.io.echo(_tr(runtime, "label.domain", value=entry.domain))
    runtime.io.echo(_tr(runtime, "label.priority", value=entry.priority))
    runtime.io.echo(_tr(runtime, "label.status", value=entry.status))
    if entry.pattern_key:
        runtime.io.echo(_tr(runtime, "label.pattern_key", value=entry.pattern_key))
    runtime.io.echo(_tr(runtime, "label.recurrence", value=str(entry.recurrence_count)))
    runtime.io.echo(_tr(runtime, "label.timestamp", value=entry.timestamp))
    if entry.see_also:
        runtime.io.echo(_tr(runtime, "label.see_also", value=", ".join(entry.see_also)))
    runtime.io.echo(_tr(runtime, "label.separator"))


def _print_analysis(runtime: PluginRuntime, result: AnalysisResult) -> None:
    if not result.pattern_groups:
        runtime.io.echo(_tr(runtime, "analyze.no_patterns"))
        return

    runtime.io.echo(_tr(runtime, "analyze.found_patterns", count=len(result.pattern_groups)))
    for group in result.pattern_groups:
        runtime.io.echo(
            _tr(
                runtime,
                "analyze.pattern_group",
                pattern=group.pattern_key,
                count=len(group.entries),
                recurrence=group.recurrence,
            )
        )

    if result.promotion_candidates:
        runtime.io.echo(_tr(runtime, "analyze.promotion_candidates", count=len(result.promotion_candidates)))
        for entry in result.promotion_candidates:
            runtime.io.echo(_tr(runtime, "analyze.candidate", id=entry.id, summary=entry.summary))


def _print_status(
    runtime: PluginRuntime,
    status: EvolutionStatus,
    config: SelfEvolveConfig | None,
) -> None:
    runtime.io.echo(_tr(runtime, "status.total", count=status.total_learnings))
    for s, count in sorted(status.status_counts.items()):
        runtime.io.echo(_tr(runtime, "status.by_status", status=s, count=count))
    runtime.io.echo(_tr(runtime, "status.rules", count=status.total_rules))
    if status.active_domains:
        runtime.io.echo(_tr(runtime, "status.domains", domains=", ".join(status.active_domains)))
