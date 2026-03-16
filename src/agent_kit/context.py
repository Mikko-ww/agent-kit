from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import questionary
import typer
from platformdirs import user_config_dir


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
        typer.secho(message, fg=typer.colors.YELLOW)

    def error(self, message: str) -> None:
        typer.secho(message, fg=typer.colors.RED, err=True)

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
        selection = questionary.checkbox(
            message,
            choices=[questionary.Choice(title=choice, value=choice) for choice in choices],
        ).ask()
        if selection is None:
            raise typer.Abort()
        return list(selection)


@dataclass(slots=True)
class AgentKitContext:
    logger: logging.Logger
    cwd: Path
    config_dir: Path
    io: InteractiveIO


def default_context_factory() -> AgentKitContext:
    return AgentKitContext(
        logger=logging.getLogger("agent-kit"),
        cwd=Path.cwd(),
        config_dir=Path(user_config_dir("agent-kit")),
        io=QuestionaryIO(),
    )
