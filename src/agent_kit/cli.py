from __future__ import annotations

from typing import Callable

import typer

from agent_kit.context import AgentKitContext, default_context_factory
from agent_kit.toolkits import DiscoveryResult, discover_toolkits


def create_app(
    *,
    discover_toolkits: Callable[[], DiscoveryResult] = discover_toolkits,
    context_factory: Callable[[], AgentKitContext] = default_context_factory,
) -> typer.Typer:
    discovery = discover_toolkits()
    app = typer.Typer(
        help="Extensible CLI for agent toolkits.",
        no_args_is_help=True,
        add_completion=False,
        epilog=_build_epilog(discovery),
    )

    for toolkit in discovery.toolkits:
        app.add_typer(
            toolkit.build_app(context_factory),
            name=toolkit.name,
            help=toolkit.help,
        )

    return app


def main() -> None:
    create_app()()


def _build_epilog(discovery: DiscoveryResult) -> str | None:
    if not discovery.failed:
        return None
    lines = ["Unavailable toolkits:"]
    for failed_toolkit in discovery.failed:
        lines.append(f"- {failed_toolkit.name}: {failed_toolkit.error}")
    return "\n".join(lines)
