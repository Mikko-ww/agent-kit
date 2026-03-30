from __future__ import annotations

import importlib
import json
import logging
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence

import pytest
import typer
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


class FakeIO:
    def __init__(self, *, text_answers=(), confirm_answers=(), multi_answers=(), select_answers=()):
        self._text_answers = deque(text_answers)
        self._confirm_answers = deque(confirm_answers)
        self._multi_answers = deque(multi_answers)
        self._select_answers = deque(select_answers)

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

    def select_one(self, message: str, choices: Sequence[str]):
        if self._select_answers:
            return self._select_answers.popleft()
        if choices:
            return choices[0]
        raise AssertionError(f"missing select answer for: {message}")


def build_app(tmp_path: Path, io: FakeIO):
    plugin_cli = require_module("self_evolve.plugin_cli")
    runtime = SimpleNamespace(
        logger=logging.getLogger("self-evolve-test"),
        cwd=tmp_path,
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
        io=io,
    )
    return plugin_cli.build_app(runtime_factory=lambda: runtime)


def setup_config(tmp_path: Path):
    config_module = require_module("self_evolve.config")
    config = config_module.SelfEvolveConfig(
        skills_target_dir=tmp_path / "skills",
        promotion_threshold=3,
        promotion_window_days=30,
        min_task_count=2,
    )
    config_module.save_config(tmp_path / "config", config)
    return config


runner = CliRunner()


class TestPluginMetadata:
    def test_plugin_metadata_output(self, tmp_path: Path):
        app = build_app(tmp_path, FakeIO())
        result = runner.invoke(app, ["--plugin-metadata"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["plugin_id"] == "self-evolve"
        assert data["api_version"] == 1
        assert data["config_version"] == 1
        assert "installed_version" in data


class TestWizard:
    def test_wizard_initializes_config(self, tmp_path: Path):
        io = FakeIO(text_answers=[str(tmp_path / "my-skills"), "3", "30", "2"])
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["wizard"])
        assert result.exit_code == 0
        assert "config" in result.output.lower() or "wizard" in result.output.lower()

        config_module = require_module("self_evolve.config")
        loaded = config_module.load_config(tmp_path / "config")
        assert loaded is not None
        assert loaded.skills_target_dir == tmp_path / "my-skills"

    def test_wizard_shows_completed_when_configured(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["wizard"])
        assert result.exit_code == 0


class TestCapture:
    def test_capture_creates_learning(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, [
            "capture",
            "--summary", "Test learning",
            "--domain", "debugging",
            "--priority", "high",
            "--pattern-key", "test-pattern",
        ])
        assert result.exit_code == 0
        assert "L-" in result.output

    def test_capture_triggers_init_when_not_configured(self, tmp_path: Path):
        io = FakeIO(text_answers=[str(tmp_path / "skills"), "3", "30", "2"])
        app = build_app(tmp_path, io)
        result = runner.invoke(app, [
            "capture",
            "--summary", "Test",
            "--domain", "testing",
        ])
        assert result.exit_code == 0


class TestList:
    def test_list_shows_entries(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "Learning 1", "-d", "debugging"])
        runner.invoke(app, ["capture", "-s", "Learning 2", "-d", "testing"])

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "Learning 1" in result.output
        assert "Learning 2" in result.output

    def test_list_shows_warning_when_empty(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0

    def test_list_filters_by_domain(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "Debug issue", "-d", "debugging"])
        runner.invoke(app, ["capture", "-s", "Test issue", "-d", "testing"])

        result = runner.invoke(app, ["list", "--domain", "debugging"])
        assert result.exit_code == 0
        assert "Debug issue" in result.output
        assert "Test issue" not in result.output


class TestAnalyze:
    def test_analyze_detects_patterns(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "Issue A1", "-d", "debugging", "--pattern-key", "env-issue"])
        runner.invoke(app, ["capture", "-s", "Issue A2", "-d", "debugging", "--pattern-key", "env-issue"])

        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0
        assert "env-issue" in result.output

    def test_analyze_no_patterns(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0


class TestPromote:
    def test_promote_creates_rule(self, tmp_path: Path):
        setup_config(tmp_path)

        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")
        entry = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="high",
            status="active",
            domain="debugging",
            summary="Check env vars",
            recurrence_count=5,
            task_ids=["t1", "t2", "t3"],
        )
        storage.save_learning(tmp_path / "data", entry)

        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["promote", "L-20260330-001", "--rule", "Validate env vars"])
        assert result.exit_code == 0
        assert "R-" in result.output

    def test_promote_warns_for_missing_entry(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["promote", "L-nonexistent", "--rule", "test"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "未找到" in result.output


class TestExtractSkill:
    def test_extract_skill_creates_skill_md(self, tmp_path: Path):
        setup_config(tmp_path)

        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")
        entry = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="high",
            status="resolved",
            domain="debugging",
            summary="Validate env vars",
            detail="Missing env vars cause startup failures.",
        )
        storage.save_learning(tmp_path / "data", entry)

        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["extract-skill", "L-20260330-001", "--name", "env-validator"])
        assert result.exit_code == 0

        skill_dir = tmp_path / "skills" / "env-validator"
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()

    def test_extract_skill_warns_for_missing_entry(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["extract-skill", "L-nonexistent", "--name", "test"])
        assert result.exit_code == 0


class TestStatus:
    def test_status_shows_overview(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "L1", "-d", "debugging"])
        runner.invoke(app, ["capture", "-s", "L2", "-d", "testing"])

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "2" in result.output

    def test_status_empty(self, tmp_path: Path):
        setup_config(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "0" in result.output


class TestHelp:
    def test_help_in_english(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("AGENT_KIT_LANG", "en")
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "self-evolving" in result.output.lower() or "capture" in result.output.lower()

    def test_help_in_chinese(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "自我进化" in result.output or "捕获" in result.output
