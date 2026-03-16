from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from agent_kit.context import AgentKitContext
from agent_kit.toolkits import ContextFactory

from agent_kit_skill_link import __version__
from agent_kit_skill_link.config import SkillLinkConfig, load_config, save_config
from agent_kit_skill_link.logic import (
    LinkResult,
    SkillStatus,
    UnlinkResult,
    discover_skill_statuses,
    ensure_supported_platform,
    link_skills,
    unlink_skills,
    validate_source_dir,
    validate_target_dir,
)


@dataclass(slots=True)
class SkillLinkToolkit:
    name: str = "skill-link"
    help: str = "Link selected local skills into a target directory."
    version: str = __version__

    def build_app(self, ctx_factory: ContextFactory) -> typer.Typer:
        app = typer.Typer(help=self.help, no_args_is_help=True, add_completion=False)

        @app.command("init")
        def init_command() -> None:
            ctx = ctx_factory()
            _run_init(ctx)

        @app.command("list")
        def list_command() -> None:
            ctx = ctx_factory()
            config = _require_config(ctx)
            _ensure_runtime_ready(ctx, config, require_target_exists=False)
            statuses = discover_skill_statuses(config)
            if not statuses:
                ctx.io.warn("No skills found in the configured source directory.")
                return
            for status in statuses:
                ctx.io.echo(f"{status.name} [{status.status}]")

        @app.command("link")
        def link_command() -> None:
            ctx = ctx_factory()
            config = _require_config(ctx)
            _ensure_runtime_ready(ctx, config, require_target_exists=True)
            statuses = discover_skill_statuses(config)
            available = [status.name for status in statuses if status.status == "not_linked"]
            if not available:
                ctx.io.warn("No skills are available to link.")
                return
            selected = ctx.io.select_many("Select skills to link", available)
            if not selected:
                ctx.io.warn("No skills selected.")
                return
            result = link_skills(config, selected)
            _report_link_result(ctx, result)
            if result.conflicts:
                raise typer.Exit(code=1)

        @app.command("unlink")
        def unlink_command() -> None:
            ctx = ctx_factory()
            config = _require_config(ctx)
            _ensure_runtime_ready(ctx, config, require_target_exists=True)
            statuses = discover_skill_statuses(config)
            removable = [status.name for status in statuses if status.status == "linked"]
            if not removable:
                ctx.io.warn("No managed links are available to unlink.")
                return
            selected = ctx.io.select_many("Select skills to unlink", removable)
            if not selected:
                ctx.io.warn("No skills selected.")
                return
            result = unlink_skills(config, selected)
            _report_unlink_result(ctx, result)

        @app.command("status")
        def status_command() -> None:
            ctx = ctx_factory()
            config = _require_config(ctx)
            source_available = config.source_dir.exists() and config.source_dir.is_dir()
            target_available = config.target_dir.exists() and config.target_dir.is_dir()
            if source_available:
                statuses = discover_skill_statuses(config)
            else:
                statuses = []
            counts = _status_counts(statuses)
            ctx.io.echo(f"source_dir: {config.source_dir}")
            ctx.io.echo(f"source_available: {_format_yes_no(source_available)}")
            ctx.io.echo(f"target_dir: {config.target_dir}")
            ctx.io.echo(f"target_available: {_format_yes_no(target_available)}")
            ctx.io.echo(f"total: {len(statuses)}")
            for name in ("linked", "not_linked", "broken_link", "conflict"):
                ctx.io.echo(f"{name}: {counts[name]}")

        return app

    def healthcheck(self, ctx: AgentKitContext) -> list[str]:
        issues: list[str] = []
        config = load_config(ctx.config_dir)
        if config is None:
            issues.append("skill-link is not configured")
            return issues
        if not config.source_dir.exists():
            issues.append(f"source directory is missing: {config.source_dir}")
        if config.target_dir.exists() and not config.target_dir.is_dir():
            issues.append(f"target path is not a directory: {config.target_dir}")
        return issues


def get_toolkit() -> SkillLinkToolkit:
    return SkillLinkToolkit()


def _require_config(ctx: AgentKitContext) -> SkillLinkConfig:
    config = load_config(ctx.config_dir)
    if config is None:
        ctx.io.warn("skill-link is not configured. Starting init.")
        config = _run_init(ctx)
    return config


def _run_init(ctx: AgentKitContext) -> SkillLinkConfig:
    ensure_supported_platform()
    existing = load_config(ctx.config_dir)
    source_dir = _prompt_for_source_dir(ctx, existing.source_dir if existing else None)
    target_dir = _prompt_for_target_dir(ctx, existing.target_dir if existing else None)
    config = SkillLinkConfig(source_dir=source_dir, target_dir=target_dir)
    path = save_config(ctx.config_dir, config)
    ctx.io.echo(f"Saved configuration to {path}")
    return config


def _prompt_for_source_dir(ctx: AgentKitContext, default: Path | None) -> Path:
    while True:
        value = ctx.io.prompt_text(
            "Source skills directory",
            default=str(default) if default else None,
        )
        source_dir = Path(value).expanduser()
        try:
            validate_source_dir(source_dir)
            return source_dir
        except ValueError as exc:
            ctx.io.error(str(exc))


def _prompt_for_target_dir(ctx: AgentKitContext, default: Path | None) -> Path:
    while True:
        value = ctx.io.prompt_text(
            "Target skills directory",
            default=str(default) if default else None,
        )
        target_dir = Path(value).expanduser()
        if target_dir.exists():
            try:
                validate_target_dir(target_dir)
                return target_dir
            except ValueError as exc:
                ctx.io.error(str(exc))
                continue
        should_create = ctx.io.confirm(
            f"Create target directory {target_dir}?",
            default=True,
        )
        if not should_create:
            ctx.io.warn("Target directory is required.")
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir


def _report_link_result(ctx: AgentKitContext, result: LinkResult) -> None:
    for name in result.linked:
        ctx.io.echo(f"linked {name}")
    for name in result.conflicts:
        ctx.io.error(f"conflict for {name}; resolve it manually")


def _report_unlink_result(ctx: AgentKitContext, result: UnlinkResult) -> None:
    for name in result.unlinked:
        ctx.io.echo(f"unlinked {name}")
    for name in result.skipped:
        ctx.io.warn(f"skipped {name}; target is not a managed link")


def _status_counts(statuses: list[SkillStatus]) -> dict[str, int]:
    counts = {
        "linked": 0,
        "not_linked": 0,
        "broken_link": 0,
        "conflict": 0,
    }
    for status in statuses:
        counts[status.status] += 1
    return counts


def _ensure_runtime_ready(
    ctx: AgentKitContext,
    config: SkillLinkConfig,
    *,
    require_target_exists: bool,
) -> None:
    try:
        validate_source_dir(config.source_dir)
        validate_target_dir(config.target_dir)
    except ValueError as exc:
        ctx.io.error(str(exc))
        raise typer.Exit(code=1) from exc

    if require_target_exists and not config.target_dir.exists():
        ctx.io.error(f"target directory does not exist: {config.target_dir}")
        raise typer.Exit(code=1)


def _format_yes_no(value: bool) -> str:
    return "yes" if value else "no"
