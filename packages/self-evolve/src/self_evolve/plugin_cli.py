"""v5 CLI——仅 init/sync/status。"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import typer

from self_evolve import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from self_evolve.config import (
    SelfEvolveConfig,
    find_project_root,
    load_config,
    rules_dir,
    save_config,
)
from self_evolve.locale import resolve_language
from self_evolve.messages import translate
from self_evolve.status_ops import get_status
from self_evolve.sync import sync_skill


@dataclass(slots=True)
class PluginRuntime:
    logger: logging.Logger
    cwd: Path
    config_root: Path
    data_root: Path
    cache_root: Path


def _default_runtime() -> PluginRuntime:
    return PluginRuntime(
        logger=logging.getLogger(PLUGIN_ID),
        cwd=Path.cwd(),
        config_root=Path(os.environ.get("AGENT_KIT_CONFIG_DIR", Path.home() / ".config" / "agent-kit")),
        data_root=Path(os.environ.get("AGENT_KIT_DATA_DIR", Path.home() / ".local" / "share" / "agent-kit")),
        cache_root=Path(os.environ.get("AGENT_KIT_CACHE_DIR", Path.home() / ".cache" / "agent-kit")),
    )


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)


def _tr(runtime: PluginRuntime, key: str, **kwargs: object) -> str:
    lang = resolve_language(runtime.config_root)
    return translate(lang, key, **kwargs)


def _prompt_template_language(runtime: PluginRuntime) -> str:
    env_lang = os.environ.get("AGENT_KIT_LANG", "")
    if env_lang in ("en", "zh-CN"):
        return env_lang
    prompt_text = _tr(runtime, "init.language.prompt")
    choice = typer.prompt(prompt_text, default="en")
    return choice if choice in ("en", "zh-CN") else "en"


def build_app(
    cwd: Path | None = None,
    runtime_factory: Callable[[], PluginRuntime] = _default_runtime,
) -> typer.Typer:
    language = resolve_language(
        Path(os.environ.get(
            "AGENT_KIT_CONFIG_DIR",
            Path.home() / ".config" / "agent-kit",
        ))
    )

    app = typer.Typer(help=_t(language, "app.help"), no_args_is_help=True)

    @app.callback(invoke_without_command=True)
    def main_callback(
        plugin_metadata: bool = typer.Option(False, "--plugin-metadata", help=_t(language, "metadata.help")),
    ) -> None:
        if plugin_metadata:
            typer.echo(json.dumps({
                "plugin_id": PLUGIN_ID,
                "installed_version": __version__,
                "api_version": API_VERSION,
                "config_version": CONFIG_VERSION,
            }))
            raise typer.Exit()

    @app.command("init", help=_t(language, "init.help"))
    def init_command() -> None:
        runtime = runtime_factory()
        if cwd is not None:
            runtime.cwd = cwd
        existing_root = find_project_root(runtime.cwd)
        if existing_root is not None and load_config(existing_root) is not None:
            typer.echo(_tr(runtime, "warning.already_initialized", path=str(existing_root)))
            return
        project_root = existing_root if existing_root is not None else runtime.cwd
        template_language = _prompt_template_language(runtime)
        rules_dir(project_root).mkdir(parents=True, exist_ok=True)
        save_config(project_root, SelfEvolveConfig(language=template_language))
        sync_skill(project_root)
        typer.echo(_tr(runtime, "init.completed"))

    @app.command("sync", help=_t(language, "sync.help"))
    def sync_command() -> None:
        runtime = runtime_factory()
        if cwd is not None:
            runtime.cwd = cwd
        project_root = find_project_root(runtime.cwd) or runtime.cwd
        cfg = load_config(project_root)
        if cfg is None:
            typer.echo(_tr(runtime, "warning.not_initialized"), err=True)
            raise typer.Exit(1)
        result = sync_skill(project_root, inline_threshold=cfg.inline_threshold)
        typer.echo(_tr(
            runtime,
            "sync.completed",
            rules_count=result.rules_count,
            strategy=result.strategy,
        ))

    @app.command("status", help=_t(language, "status.help"))
    def status_command() -> None:
        runtime = runtime_factory()
        if cwd is not None:
            runtime.cwd = cwd
        project_root = find_project_root(runtime.cwd) or runtime.cwd
        cfg = load_config(project_root)
        if cfg is None:
            typer.echo(_tr(runtime, "warning.not_initialized"), err=True)
            raise typer.Exit(1)
        status = get_status(project_root)
        total = sum(status.rule_counts.values())
        counts_str = ", ".join(f"{k}={v}" for k, v in sorted(status.rule_counts.items()))
        typer.echo(_tr(runtime, "status.rules", total=total, counts=counts_str or "0"))

    return app


def main() -> None:
    app = build_app()
    app()
