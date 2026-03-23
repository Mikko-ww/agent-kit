from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import questionary
import typer

from skills_link import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from skills_link.config import SkillLinkConfig, TargetConfig, load_config, save_config
from skills_link.logic import (
    LinkResult,
    SkillStatus,
    TargetSummary,
    UnlinkResult,
    add_target,
    discover_skill_statuses,
    ensure_supported_platform,
    link_skills,
    remove_target,
    summarize_targets,
    unlink_skills,
    update_target,
    validate_source_dir,
    validate_target_dir,
)


class InteractiveIO(Protocol):
    def echo(self, message: str) -> None: ...

    def warn(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def prompt_text(self, message: str, default: str | None = None) -> str: ...

    def confirm(self, message: str, default: bool = False) -> bool: ...

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
    app = typer.Typer(
        help="Link selected local skills into one or more target directories.",
        no_args_is_help=True,
        add_completion=False,
    )
    target_app = typer.Typer(help="Manage registered target directories.", no_args_is_help=True)
    app.add_typer(target_app, name="target")

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

    @app.command("init")
    def init_command() -> None:
        runtime = runtime_factory()
        _run_init(runtime)

    @app.command("list")
    def list_command(
        target_names: list[str] = typer.Option([], "--target", help="Limit to specific target names."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        try:
            statuses = discover_skill_statuses(config, target_names=_target_names_or_none(target_names))
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        if not statuses:
            runtime.io.warn("No skills found in the configured source directory.")
            return
        for status in statuses:
            runtime.io.echo(_format_skill_status(status))

    @app.command("link")
    def link_command(
        target_names: list[str] = typer.Option([], "--target", help="Limit to specific target names."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        selected_targets = _target_names_or_none(target_names)
        try:
            statuses = discover_skill_statuses(config, target_names=selected_targets)
            available = [
                status.name
                for status in statuses
                if any(target.status == "not_linked" for target in status.target_statuses)
            ]
            if not available:
                runtime.io.warn("No skills are available to link.")
                return
            selected = runtime.io.select_many("Select skills to link", available)
            if not selected:
                runtime.io.warn("No skills selected.")
                return
            result = link_skills(config, selected, target_names=selected_targets)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        _report_link_result(runtime, result)
        if result.conflicts:
            raise typer.Exit(code=1)

    @app.command("unlink")
    def unlink_command(
        target_names: list[str] = typer.Option([], "--target", help="Limit to specific target names."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        selected_targets = _target_names_or_none(target_names)
        try:
            statuses = discover_skill_statuses(config, target_names=selected_targets)
            removable = [
                status.name
                for status in statuses
                if any(target.status == "linked" for target in status.target_statuses)
            ]
            if not removable:
                runtime.io.warn("No managed links are available to unlink.")
                return
            selected = runtime.io.select_many("Select skills to unlink", removable)
            if not selected:
                runtime.io.warn("No skills selected.")
                return
            result = unlink_skills(config, selected, target_names=selected_targets)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        _report_unlink_result(runtime, result)

    @app.command("status")
    def status_command(
        target_names: list[str] = typer.Option([], "--target", help="Limit to specific target names."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        source_available = config.source_dir.exists() and config.source_dir.is_dir()
        runtime.io.echo(f"source_dir: {config.source_dir}")
        runtime.io.echo(f"source_available: {_format_yes_no(source_available)}")
        try:
            summaries = _load_target_summaries(config, target_names, source_available=source_available)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"targets: {len(summaries)}")
        for summary in summaries:
            _echo_target_summary(runtime, summary)

    @target_app.command("list")
    def target_list_command() -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        source_available = config.source_dir.exists() and config.source_dir.is_dir()
        try:
            summaries = _load_target_summaries(config, (), source_available=source_available)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        for summary in summaries:
            _echo_target_registry(runtime, summary)

    @target_app.command("add")
    def target_add_command(
        name: str = typer.Option(..., "--name", help="Target name."),
        path: str = typer.Option(..., "--path", help="Target directory path."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        try:
            target_path = _prepare_target_path(runtime, Path(_normalize_path_text(path)).expanduser())
            updated = add_target(config, TargetConfig(name=name, path=target_path))
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"Saved configuration to {saved_path}")

    @target_app.command("update")
    def target_update_command(
        name: str = typer.Option(..., "--name", help="Existing target name."),
        new_name: str | None = typer.Option(None, "--new-name", help="New target name."),
        path: str | None = typer.Option(None, "--path", help="New target directory path."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        if new_name is None and path is None:
            runtime.io.error("at least one of --new-name or --path is required")
            raise typer.Exit(code=1)

        new_path = Path(_normalize_path_text(path)).expanduser() if path is not None else None
        try:
            updated = update_target(config, name, new_name=new_name, new_path=new_path)
            if new_path is not None:
                _prepare_target_path(runtime, new_path)
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"Saved configuration to {saved_path}")

    @target_app.command("remove")
    def target_remove_command(
        name: str = typer.Option(..., "--name", help="Target name."),
    ) -> None:
        runtime = runtime_factory()
        config = _require_config(runtime)
        try:
            updated = remove_target(config, name)
            saved_path = save_config(runtime.config_root, updated)
        except ValueError as exc:
            _exit_with_error(runtime, exc)
        runtime.io.echo(f"Saved configuration to {saved_path}")

    return app


def main() -> None:
    build_app()()


def _require_config(runtime: PluginRuntime) -> SkillLinkConfig:
    config = load_config(runtime.config_root)
    if config is None:
        runtime.io.warn("skills-link is not configured. Starting init.")
        config = _run_init(runtime)
    return config


def _run_init(runtime: PluginRuntime) -> SkillLinkConfig:
    ensure_supported_platform()
    existing = load_config(runtime.config_root)
    default_target = existing.targets[0] if existing and existing.targets else None
    source_dir = _prompt_for_source_dir(runtime, existing.source_dir if existing else None)
    target_name = _prompt_for_target_name(runtime, default_target.name if default_target else None)
    target_path = _prompt_for_target_path(runtime, default_target.path if default_target else None)
    config = SkillLinkConfig(
        source_dir=source_dir,
        targets=[TargetConfig(name=target_name, path=target_path)],
    )
    path = save_config(runtime.config_root, config)
    runtime.io.echo(f"Saved configuration to {path}")
    return config


def _prompt_for_source_dir(runtime: PluginRuntime, default: Path | None) -> Path:
    while True:
        value = runtime.io.prompt_text(
            "Source skills directory",
            default=str(default) if default else None,
        )
        source_dir = Path(_normalize_path_text(value)).expanduser()
        try:
            validate_source_dir(source_dir)
            return source_dir
        except ValueError as exc:
            runtime.io.error(str(exc))


def _prompt_for_target_name(runtime: PluginRuntime, default: str | None) -> str:
    while True:
        value = runtime.io.prompt_text(
            "Initial target name",
            default=default,
        ).strip()
        if value:
            return value
        runtime.io.error("target name is required")


def _prompt_for_target_path(runtime: PluginRuntime, default: Path | None) -> Path:
    while True:
        value = runtime.io.prompt_text(
            "Initial target directory",
            default=str(default) if default else None,
        )
        target_path = Path(_normalize_path_text(value)).expanduser()
        try:
            return _prepare_target_path(runtime, target_path)
        except ValueError as exc:
            runtime.io.error(str(exc))


def _prepare_target_path(runtime: PluginRuntime, target_path: Path) -> Path:
    if target_path.exists():
        validate_target_dir(target_path)
        return target_path

    should_create = runtime.io.confirm(
        f"Create target directory {target_path}?",
        default=True,
    )
    if not should_create:
        raise ValueError(f"target directory does not exist: {target_path}")
    target_path.mkdir(parents=True, exist_ok=True)
    return target_path


def _report_link_result(runtime: PluginRuntime, result: LinkResult) -> None:
    for item in result.linked:
        runtime.io.echo(f"linked {item.skill_name} -> {item.target_name}")
    for item in result.conflicts:
        runtime.io.error(f"conflict {item.skill_name} -> {item.target_name}; resolve it manually")


def _report_unlink_result(runtime: PluginRuntime, result: UnlinkResult) -> None:
    for item in result.unlinked:
        runtime.io.echo(f"unlinked {item.skill_name} -> {item.target_name}")
    for item in result.skipped:
        runtime.io.warn(f"skipped {item.skill_name} -> {item.target_name}; target is not a managed link")


def _format_skill_status(status: SkillStatus) -> str:
    if len(status.target_statuses) == 1:
        return f"{status.name} [{status.target_statuses[0].status}]"

    statuses = ", ".join(
        f"{target.target_name}={target.status}"
        for target in status.target_statuses
    )
    return f"{status.name} [{statuses}]"


def _echo_target_summary(runtime: PluginRuntime, summary: TargetSummary) -> None:
    runtime.io.echo(f"[{summary.name}]")
    runtime.io.echo(f"path: {summary.path}")
    runtime.io.echo(f"available: {_format_yes_no(summary.available)}")
    runtime.io.echo(f"linked: {summary.linked}")
    runtime.io.echo(f"not_linked: {summary.not_linked}")
    runtime.io.echo(f"broken_link: {summary.broken_link}")
    runtime.io.echo(f"conflict: {summary.conflict}")


def _echo_target_registry(runtime: PluginRuntime, summary: TargetSummary) -> None:
    runtime.io.echo(f"[{summary.name}]")
    runtime.io.echo(f"path: {summary.path}")
    runtime.io.echo(f"available: {_format_yes_no(summary.available)}")
    runtime.io.echo(f"managed_links: {summary.managed_links}")
    runtime.io.echo(f"conflicts: {summary.conflict}")
    runtime.io.echo(f"broken_links: {summary.broken_link}")


def _load_target_summaries(
    config: SkillLinkConfig,
    target_names: Sequence[str],
    *,
    source_available: bool,
) -> list[TargetSummary]:
    selected_names = _target_names_or_none(target_names)
    if source_available:
        return summarize_targets(config, target_names=selected_names)

    summaries: list[TargetSummary] = []
    for target in _filter_targets(config, selected_names):
        summaries.append(
            TargetSummary(
                name=target.name,
                path=target.path,
                available=target.path.exists() and target.path.is_dir(),
                managed_links=0,
                linked=0,
                not_linked=0,
                broken_link=0,
                conflict=0,
            )
        )
    return summaries


def _filter_targets(config: SkillLinkConfig, target_names: list[str] | None) -> list[TargetConfig]:
    if not target_names:
        return list(config.targets)

    targets_by_name = {target.name: target for target in config.targets}
    filtered: list[TargetConfig] = []
    missing: list[str] = []

    for name in target_names:
        target = targets_by_name.get(name)
        if target is None:
            missing.append(name)
            continue
        if target not in filtered:
            filtered.append(target)

    if missing:
        raise ValueError(f"unknown target(s): {', '.join(missing)}")
    return filtered


def _target_names_or_none(target_names: Sequence[str]) -> list[str] | None:
    if not target_names:
        return None
    return list(target_names)


def _normalize_path_text(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1]
    return normalized


def _exit_with_error(runtime: PluginRuntime, exc: ValueError) -> None:
    runtime.io.error(str(exc))
    raise typer.Exit(code=1) from exc


def _format_yes_no(value: bool) -> str:
    return "yes" if value else "no"
