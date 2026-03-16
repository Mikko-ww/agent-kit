from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Callable, Iterable, Protocol, Sequence, runtime_checkable

import typer

from agent_kit.context import AgentKitContext

TOOLKIT_ENTRY_POINT_GROUP = "agent_kit.toolkits"

ContextFactory = Callable[[], AgentKitContext]


@runtime_checkable
class Toolkit(Protocol):
    name: str
    help: str
    version: str

    def build_app(self, ctx_factory: ContextFactory) -> typer.Typer: ...

    def healthcheck(self, ctx: AgentKitContext) -> list[str]: ...


@dataclass(slots=True)
class FailedToolkit:
    name: str
    error: str


@dataclass(slots=True)
class DiscoveryResult:
    toolkits: list[Toolkit]
    failed: list[FailedToolkit]


def discover_toolkits(
    entry_points_provider: Callable[[], Iterable[object]] | None = None,
) -> DiscoveryResult:
    provider = entry_points_provider or _default_entry_points
    loaded_toolkits: list[Toolkit] = []
    failed_toolkits: list[FailedToolkit] = []

    for entry_point in provider():
        try:
            candidate = entry_point.load()
            toolkit = candidate() if callable(candidate) and not _looks_like_toolkit(candidate) else candidate
            if not _looks_like_toolkit(toolkit):
                raise TypeError("entry point did not resolve to a toolkit")
            loaded_toolkits.append(toolkit)
        except Exception as exc:  # pragma: no cover - exercised via tests
            failed_toolkits.append(FailedToolkit(name=getattr(entry_point, "name", "unknown"), error=str(exc)))

    loaded_toolkits.sort(key=lambda toolkit: toolkit.name)
    failed_toolkits.sort(key=lambda toolkit: toolkit.name)
    return DiscoveryResult(toolkits=loaded_toolkits, failed=failed_toolkits)


def _default_entry_points() -> Sequence[object]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        return list(discovered.select(group=TOOLKIT_ENTRY_POINT_GROUP))
    return list(discovered.get(TOOLKIT_ENTRY_POINT_GROUP, []))


def _looks_like_toolkit(candidate: object) -> bool:
    return all(
        hasattr(candidate, attribute)
        for attribute in ("name", "help", "version", "build_app")
    )
