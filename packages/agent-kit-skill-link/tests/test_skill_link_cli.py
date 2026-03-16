from __future__ import annotations

import importlib
import logging
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def write_skill(base: Path, name: str) -> Path:
    skill_dir = base / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return skill_dir


class FakeIO:
    def __init__(self, *, text_answers=(), confirm_answers=(), multi_answers=()):
        self._text_answers = deque(text_answers)
        self._confirm_answers = deque(confirm_answers)
        self._multi_answers = deque(multi_answers)

    def echo(self, message: str) -> None:
        typer.echo(message)

    def warn(self, message: str) -> None:
        typer.echo(message)

    def error(self, message: str) -> None:
        typer.echo(message)

    def prompt_text(self, message: str, default: str | None = None) -> str:
        if self._text_answers:
            return self._text_answers.popleft()
        if default is not None:
            return default
        raise AssertionError(f"missing text answer for: {message}")

    def confirm(self, message: str, default: bool = False) -> bool:
        if self._confirm_answers:
            return self._confirm_answers.popleft()
        return default

    def select_many(self, message: str, choices):
        if self._multi_answers:
            return list(self._multi_answers.popleft())
        return []


def build_app(tmp_path: Path, io: FakeIO):
    toolkit_module = require_module("agent_kit_skill_link.toolkit")
    context = SimpleNamespace(
        logger=logging.getLogger("skill-link-test"),
        cwd=tmp_path,
        config_dir=tmp_path / "config",
        io=io,
    )
    return toolkit_module.get_toolkit().build_app(lambda: context)


def test_list_auto_runs_init_when_not_configured(tmp_path: Path):
    source_dir = tmp_path / "skills"
    target_dir = tmp_path / "linked"
    source_dir.mkdir()
    write_skill(source_dir, "alpha")
    io = FakeIO(
        text_answers=[str(source_dir), str(target_dir)],
        confirm_answers=[True],
    )
    app = build_app(tmp_path, io)

    result = CliRunner().invoke(app, ["list"])

    assert result.exit_code == 0
    assert "alpha" in result.output
    assert (tmp_path / "config" / "config.toml").exists()
    assert target_dir.exists()


def test_link_and_unlink_commands_manage_symlinks(tmp_path: Path):
    config_module = require_module("agent_kit_skill_link.config")

    source_dir = tmp_path / "skills"
    target_dir = tmp_path / "linked"
    source_dir.mkdir()
    target_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    config_module.save_config(
        tmp_path / "config",
        config_module.SkillLinkConfig(source_dir=source_dir, target_dir=target_dir),
    )
    io = FakeIO(multi_answers=[["alpha"], ["alpha"]])
    app = build_app(tmp_path, io)
    runner = CliRunner()

    link_result = runner.invoke(app, ["link"])
    assert link_result.exit_code == 0
    assert (target_dir / "alpha").is_symlink()
    assert (target_dir / "alpha").resolve() == alpha.resolve()

    status_result = runner.invoke(app, ["status"])
    unlink_result = runner.invoke(app, ["unlink"])

    assert "source_available: yes" in status_result.output
    assert "target_available: yes" in status_result.output
    assert "linked: 1" in status_result.output
    assert unlink_result.exit_code == 0
    assert not (target_dir / "alpha").exists()
