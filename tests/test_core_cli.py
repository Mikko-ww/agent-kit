from __future__ import annotations

import importlib
import types

import pytest
import typer
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


class FakeToolkit:
    name = "demo"
    help = "Demo toolkit"
    version = "1.0.0"

    def build_app(self, ctx_factory):
        app = typer.Typer(help="Demo toolkit")

        @app.command()
        def ping():
            ctx = ctx_factory()
            typer.echo(f"pong:{ctx.marker}")

        return app


def test_create_app_mounts_loaded_toolkit_commands():
    cli = require_module("agent_kit.cli")
    app = cli.create_app(
        discover_toolkits=lambda: types.SimpleNamespace(toolkits=[FakeToolkit()], failed=[]),
        context_factory=lambda: types.SimpleNamespace(marker="ok"),
    )

    result = CliRunner().invoke(app, ["demo", "ping"])

    assert result.exit_code == 0
    assert "pong:ok" in result.output


def test_help_reports_failed_toolkits_without_blocking_loaded_ones():
    cli = require_module("agent_kit.cli")
    app = cli.create_app(
        discover_toolkits=lambda: types.SimpleNamespace(
            toolkits=[FakeToolkit()],
            failed=[types.SimpleNamespace(name="broken", error="boom")],
        ),
        context_factory=lambda: types.SimpleNamespace(marker="ok"),
    )
    runner = CliRunner()

    help_result = runner.invoke(app, ["--help"])
    ping_result = runner.invoke(app, ["demo", "ping"])

    assert help_result.exit_code == 0
    assert "broken" in help_result.output
    assert "boom" in help_result.output
    assert "demo" in help_result.output
    assert ping_result.exit_code == 0


def test_discover_toolkits_collects_load_errors():
    toolkits = require_module("agent_kit.toolkits")

    class FakeEntryPoint:
        def __init__(self, name, loader):
            self.name = name
            self._loader = loader

        def load(self):
            return self._loader()

    ok_entry = FakeEntryPoint("demo", lambda: FakeToolkit())
    broken_entry = FakeEntryPoint("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    result = toolkits.discover_toolkits(lambda: [ok_entry, broken_entry])

    assert [toolkit.name for toolkit in result.toolkits] == ["demo"]
    assert len(result.failed) == 1
    assert result.failed[0].name == "broken"
    assert "boom" in result.failed[0].error


def test_questionary_io_omits_none_default(monkeypatch):
    context_module = require_module("agent_kit.context")
    captured = {}

    class FakePrompt:
        def ask(self):
            return "value"

    def fake_text(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs
        return FakePrompt()

    monkeypatch.setattr(context_module.questionary, "text", fake_text)

    value = context_module.QuestionaryIO().prompt_text("Source skills directory")

    assert value == "value"
    assert captured["message"] == "Source skills directory"
    assert "default" not in captured["kwargs"]
