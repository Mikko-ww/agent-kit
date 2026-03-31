from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import click
import typer

from self_evolve import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from self_evolve.candidate_ops import accept_candidate, edit_candidate, filter_candidates, reject_candidate
from self_evolve.config import LegacyLayoutError, SelfEvolveConfig, find_project_root, load_config
from self_evolve.detector import run_detection
from self_evolve.locale import normalize_language, resolve_language
from self_evolve.messages import translate
from self_evolve.rule_ops import add_rule, edit_rule, filter_rules, retire_rule
from self_evolve.session_ops import initialize_project, record_session
from self_evolve.status_ops import get_status
from self_evolve.storage import load_candidate, load_rule
from self_evolve.sync import sync_skill


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
    app = typer.Typer(help=_t(language, "app.help"), no_args_is_help=True, add_completion=False)
    session_app = typer.Typer(help=_t(language, "session.app.help"), no_args_is_help=True)
    detect_app = typer.Typer(help=_t(language, "detect.app.help"), no_args_is_help=True)
    candidate_app = typer.Typer(help=_t(language, "candidate.app.help"), no_args_is_help=True)
    rule_app = typer.Typer(help=_t(language, "rule.app.help"), no_args_is_help=True)
    app.add_typer(session_app, name="session")
    app.add_typer(detect_app, name="detect")
    app.add_typer(candidate_app, name="candidate")
    app.add_typer(rule_app, name="rule")

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

    @app.command("init", help=_t(language, "init.help"))
    def init_command() -> None:
        runtime = runtime_factory()
        try:
            project_root = runtime.cwd
            existing_root = find_project_root(project_root)
            if existing_root is not None and load_config(existing_root) is not None:
                typer.echo(_tr(runtime, "warning.already_initialized", path=str(existing_root)))
                return
            template_language = _prompt_template_language(runtime)
            initialize_project(project_root, SelfEvolveConfig(language=template_language))
            sync_skill(project_root)
            typer.echo(_tr(runtime, "init.completed"))
        except LegacyLayoutError:
            _raise_legacy_error(runtime)

    @session_app.command("record", help=_t(language, "session.record.help"))
    def session_record_command(
        summary: str = typer.Option(..., "--summary"),
        domain: str = typer.Option(..., "--domain"),
        outcome: str = typer.Option(..., "--outcome"),
        source: str = typer.Option("agent", "--source"),
        observation: list[str] = typer.Option([], "--observation"),
        decision: list[str] = typer.Option([], "--decision"),
        fix: list[str] = typer.Option([], "--fix"),
        lesson: list[str] = typer.Option([], "--lesson"),
        file: list[str] = typer.Option([], "--file"),
        tag: list[str] = typer.Option([], "--tag"),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        session = record_session(
            project_root,
            summary=summary,
            domain=domain,
            outcome=outcome,
            source=source,
            observations=list(observation),
            decisions=list(decision),
            fixes=list(fix),
            lessons=list(lesson),
            files=list(file),
            tags=list(tag),
        )
        typer.echo(_tr(runtime, "saved.session", id=session.id))

    @detect_app.command("run", help=_t(language, "detect.run.help"))
    def detect_run_command(session_id: list[str] = typer.Option([], "--session-id")) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        config = _require_config(runtime, project_root)
        result = run_detection(project_root, config, session_ids=list(session_id) or None)
        for candidate in result.candidates:
            typer.echo(_tr(runtime, "saved.candidate", id=candidate.id))
        for rule in result.auto_accepted_rules:
            typer.echo(_tr(runtime, "saved.rule", id=rule.id))
        typer.echo(_tr(runtime, "detect.completed", sessions=len(result.processed_session_ids), candidates=len(result.candidates)))

    @candidate_app.command("list", help=_t(language, "candidate.list.help"))
    def candidate_list_command(
        status: str | None = typer.Option(None, "--status"),
        domain: str | None = typer.Option(None, "--domain"),
        tag: str | None = typer.Option(None, "--tag"),
        keyword: str | None = typer.Option(None, "--keyword"),
        limit: int = typer.Option(20, "--limit"),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        items = filter_candidates(project_root, status=status, domain=domain, tag=tag, keyword=keyword, limit=limit)
        if not items:
            typer.echo(_tr(runtime, "list.empty"))
            return
        for item in items:
            typer.echo(f"[{item.status}] {item.id} {item.title} :: {item.statement}")

    @candidate_app.command("show", help=_t(language, "candidate.show.help"))
    def candidate_show_command(candidate_id: str) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        item = load_candidate(project_root, candidate_id)
        if item is None:
            typer.echo(_tr(runtime, "warning.not_found", kind="candidate", id=candidate_id))
            raise typer.Exit(code=1)
        _print_candidate(item)

    @candidate_app.command("accept", help=_t(language, "candidate.accept.help"))
    def candidate_accept_command(candidate_id: str) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        rule = accept_candidate(project_root, candidate_id)
        if rule is None:
            typer.echo(_tr(runtime, "warning.not_found", kind="candidate", id=candidate_id))
            raise typer.Exit(code=1)
        typer.echo(_tr(runtime, "saved.rule", id=rule.id))

    @candidate_app.command("reject", help=_t(language, "candidate.reject.help"))
    def candidate_reject_command(candidate_id: str) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        item = reject_candidate(project_root, candidate_id)
        if item is None:
            typer.echo(_tr(runtime, "warning.not_found", kind="candidate", id=candidate_id))
            raise typer.Exit(code=1)
        typer.echo(_tr(runtime, "rejected.candidate", id=item.id))

    @candidate_app.command("edit", help=_t(language, "candidate.edit.help"))
    def candidate_edit_command(
        candidate_id: str,
        title: str | None = typer.Option(None, "--title"),
        statement: str | None = typer.Option(None, "--statement"),
        rationale: str | None = typer.Option(None, "--rationale"),
        domain: str | None = typer.Option(None, "--domain"),
        tag: list[str] | None = typer.Option(None, "--tag"),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        item = edit_candidate(project_root, candidate_id, title=title, statement=statement, rationale=rationale, domain=domain, tags=tag)
        if item is None:
            typer.echo(_tr(runtime, "warning.not_found", kind="candidate", id=candidate_id))
            raise typer.Exit(code=1)
        typer.echo(_tr(runtime, "updated.candidate", id=item.id))

    @rule_app.command("add", help=_t(language, "rule.add.help"))
    def rule_add_command(
        title: str = typer.Option(..., "--title"),
        statement: str = typer.Option(..., "--statement"),
        rationale: str = typer.Option(..., "--rationale"),
        domain: str = typer.Option(..., "--domain"),
        tag: list[str] = typer.Option([], "--tag"),
        source_session_id: list[str] = typer.Option([], "--source-session-id"),
        source_candidate_id: list[str] = typer.Option([], "--source-candidate-id"),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        rule = add_rule(
            project_root,
            title=title,
            statement=statement,
            rationale=rationale,
            domain=domain,
            tags=list(tag),
            source_session_ids=list(source_session_id),
            source_candidate_ids=list(source_candidate_id),
        )
        typer.echo(_tr(runtime, "saved.rule", id=rule.id))

    @rule_app.command("list", help=_t(language, "rule.list.help"))
    def rule_list_command(
        status: str | None = typer.Option(None, "--status"),
        domain: str | None = typer.Option(None, "--domain"),
        tag: str | None = typer.Option(None, "--tag"),
        keyword: str | None = typer.Option(None, "--keyword"),
        limit: int = typer.Option(20, "--limit"),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        items = filter_rules(project_root, status=status, domain=domain, tag=tag, keyword=keyword, limit=limit)
        if not items:
            typer.echo(_tr(runtime, "list.empty"))
            return
        for item in items:
            typer.echo(f"[{item.status}] {item.id} {item.title} :: {item.statement}")

    @rule_app.command("show", help=_t(language, "rule.show.help"))
    def rule_show_command(rule_id: str) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        item = load_rule(project_root, rule_id)
        if item is None:
            typer.echo(_tr(runtime, "warning.not_found", kind="rule", id=rule_id))
            raise typer.Exit(code=1)
        _print_rule(item)

    @rule_app.command("edit", help=_t(language, "rule.edit.help"))
    def rule_edit_command(
        rule_id: str,
        title: str | None = typer.Option(None, "--title"),
        statement: str | None = typer.Option(None, "--statement"),
        rationale: str | None = typer.Option(None, "--rationale"),
        domain: str | None = typer.Option(None, "--domain"),
        tag: list[str] | None = typer.Option(None, "--tag"),
        revision_of: str | None = typer.Option(None, "--revision-of"),
    ) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        item = edit_rule(project_root, rule_id, title=title, statement=statement, rationale=rationale, domain=domain, tags=tag, revision_of=revision_of)
        if item is None:
            typer.echo(_tr(runtime, "warning.not_found", kind="rule", id=rule_id))
            raise typer.Exit(code=1)
        typer.echo(_tr(runtime, "updated.rule", id=item.id))

    @rule_app.command("retire", help=_t(language, "rule.retire.help"))
    def rule_retire_command(rule_id: str) -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        item = retire_rule(project_root, rule_id)
        if item is None:
            typer.echo(_tr(runtime, "warning.not_found", kind="rule", id=rule_id))
            raise typer.Exit(code=1)
        typer.echo(_tr(runtime, "retired.rule", id=item.id))

    @app.command("sync", help=_t(language, "sync.help"))
    def sync_command() -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        config = _require_config(runtime, project_root)
        result = sync_skill(project_root, inline_threshold=config.inline_threshold)
        typer.echo(_tr(runtime, "sync.completed", count=result.rules_count, path=str(result.path), strategy=result.strategy))

    @app.command("status", help=_t(language, "status.help"))
    def status_command() -> None:
        runtime = runtime_factory()
        project_root = _require_project(runtime)
        status = get_status(project_root)
        typer.echo(_tr(runtime, "status.sessions", total=status.total_sessions, processed=status.processed_sessions, pending=status.pending_sessions))
        typer.echo(_tr(runtime, "status.candidates", counts=_format_counts(status.candidate_counts)))
        typer.echo(_tr(runtime, "status.rules", counts=_format_counts(status.rule_counts)))

    return app


def main() -> None:
    build_app()()


def _runtime_language(runtime: PluginRuntime) -> str:
    return resolve_language(runtime.config_root)


def _prompt_template_language(runtime: PluginRuntime) -> str:
    default_language = normalize_language(os.environ.get("AGENT_KIT_LANG")) or "en"
    selected = typer.prompt(
        _tr(runtime, "init.language.prompt"),
        default=default_language,
        show_default=True,
        type=click.Choice(["en", "zh-CN"], case_sensitive=False),
    )
    normalized = normalize_language(selected)
    if normalized is None:
        return default_language
    return normalized


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)


def _tr(runtime: PluginRuntime, key: str, **kwargs: object) -> str:
    return translate(_runtime_language(runtime), key, **kwargs)


def _require_project(runtime: PluginRuntime) -> Path:
    try:
        project_root = find_project_root(runtime.cwd)
        if project_root is None:
            typer.echo(_tr(runtime, "warning.not_initialized"))
            raise typer.Exit(code=1)
        config = load_config(project_root)
        if config is None:
            typer.echo(_tr(runtime, "warning.not_initialized"))
            raise typer.Exit(code=1)
        return project_root
    except LegacyLayoutError:
        _raise_legacy_error(runtime)
        raise typer.Exit(code=1)


def _require_config(runtime: PluginRuntime, project_root: Path) -> SelfEvolveConfig:
    try:
        config = load_config(project_root)
        if config is None:
            typer.echo(_tr(runtime, "warning.not_initialized"))
            raise typer.Exit(code=1)
        return config
    except LegacyLayoutError:
        _raise_legacy_error(runtime)
        raise typer.Exit(code=1)


def _raise_legacy_error(runtime: PluginRuntime) -> None:
    typer.echo(_tr(runtime, "warning.legacy_layout"))
    raise typer.Exit(code=1)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _print_candidate(candidate) -> None:
    typer.echo(f"{candidate.id} [{candidate.status}]")
    typer.echo(f"title: {candidate.title}")
    typer.echo(f"statement: {candidate.statement}")
    typer.echo(f"rationale: {candidate.rationale}")
    typer.echo(f"domain: {candidate.domain}")
    typer.echo(f"confidence: {candidate.confidence}")


def _print_rule(rule) -> None:
    typer.echo(f"{rule.id} [{rule.status}]")
    typer.echo(f"title: {rule.title}")
    typer.echo(f"statement: {rule.statement}")
    typer.echo(f"rationale: {rule.rationale}")
    typer.echo(f"domain: {rule.domain}")
