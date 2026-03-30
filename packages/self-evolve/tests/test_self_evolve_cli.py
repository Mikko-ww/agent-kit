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


def setup_project(tmp_path: Path):
    """创建已初始化的项目结构。"""
    config_module = require_module("self_evolve.config")
    config = config_module.SelfEvolveConfig(
        targets=["cursor", "copilot", "codex"],
        promotion_threshold=3,
        promotion_window_days=30,
        min_task_count=2,
    )
    config_module.save_config(tmp_path, config)
    # 创建 .self-evolve 目录
    (tmp_path / ".self-evolve").mkdir(exist_ok=True)
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
        assert data["config_version"] == 2
        assert "installed_version" in data


class TestInit:
    def test_init_creates_project(self, tmp_path: Path):
        io = FakeIO(
            multi_answers=[["cursor", "copilot"]],
            text_answers=["3", "2"],
        )
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "cursor" in result.output.lower() or "copilot" in result.output.lower()

        config_module = require_module("self_evolve.config")
        loaded = config_module.load_config(tmp_path)
        assert loaded is not None
        assert "cursor" in loaded.targets

    def test_init_warns_when_already_initialized(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0


class TestCapture:
    def test_capture_creates_learning(self, tmp_path: Path):
        setup_project(tmp_path)
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

    def test_capture_warns_when_not_initialized(self, tmp_path: Path):
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, [
            "capture",
            "--summary", "Test",
            "--domain", "testing",
        ])
        assert result.exit_code == 0
        assert "init" in result.output.lower() or "初始化" in result.output


class TestList:
    def test_list_shows_entries(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "Learning 1", "-d", "debugging"])
        runner.invoke(app, ["capture", "-s", "Learning 2", "-d", "testing"])

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "Learning 1" in result.output
        assert "Learning 2" in result.output

    def test_list_shows_warning_when_empty(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0

    def test_list_filters_by_domain(self, tmp_path: Path):
        setup_project(tmp_path)
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
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "Issue A1", "-d", "debugging", "--pattern-key", "env-issue"])
        runner.invoke(app, ["capture", "-s", "Issue A2", "-d", "debugging", "--pattern-key", "env-issue"])

        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0
        assert "env-issue" in result.output

    def test_analyze_no_patterns(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0


class TestPromote:
    def test_promote_creates_rule(self, tmp_path: Path):
        setup_project(tmp_path)

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
        storage.save_learning(tmp_path, entry)

        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["promote", "L-20260330-001", "--rule", "Validate env vars"])
        assert result.exit_code == 0
        assert "R-" in result.output

    def test_promote_warns_for_missing_entry(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["promote", "L-nonexistent", "--rule", "test"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "未找到" in result.output


class TestSync:
    def test_sync_writes_agent_files(self, tmp_path: Path):
        setup_project(tmp_path)

        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")
        rules = [
            models.PromotedRule(
                id="R-001",
                source_learning_id="L-001",
                rule="Always validate inputs",
                domain="security",
                created_at="2026-03-30T12:00:00Z",
            ),
        ]
        storage.save_rules(tmp_path, rules)

        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
        assert "cursor" in result.output.lower() or "copilot" in result.output.lower()

        assert (tmp_path / ".cursor" / "rules" / "self-evolve.mdc").exists()

    def test_sync_with_no_rules(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0


class TestEvolve:
    def test_evolve_runs_full_cycle(self, tmp_path: Path):
        config_module = require_module("self_evolve.config")
        config = config_module.SelfEvolveConfig(
            targets=["cursor"],
            promotion_threshold=2,
            min_task_count=2,
        )
        config_module.save_config(tmp_path, config)
        (tmp_path / ".self-evolve").mkdir(exist_ok=True)

        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")
        e1 = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="high",
            status="active",
            domain="debugging",
            summary="Check env vars",
            pattern_key="env-check",
            recurrence_count=3,
            task_ids=["t1", "t2"],
        )
        e2 = models.LearningEntry(
            id="L-20260330-002",
            timestamp="2026-03-30T12:01:00Z",
            priority="high",
            status="active",
            domain="debugging",
            summary="Also check env vars",
            pattern_key="env-check",
            recurrence_count=3,
            task_ids=["t1", "t2"],
        )
        storage.save_learning(tmp_path, e1)
        storage.save_learning(tmp_path, e2)

        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["evolve"])
        assert result.exit_code == 0
        assert "R-" in result.output

    def test_evolve_no_eligible(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "Single learning", "-d", "testing"])

        result = runner.invoke(app, ["evolve"])
        assert result.exit_code == 0


class TestStatus:
    def test_status_shows_overview(self, tmp_path: Path):
        setup_project(tmp_path)
        io = FakeIO()
        app = build_app(tmp_path, io)

        runner.invoke(app, ["capture", "-s", "L1", "-d", "debugging"])
        runner.invoke(app, ["capture", "-s", "L2", "-d", "testing"])

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "2" in result.output

    def test_status_empty(self, tmp_path: Path):
        setup_project(tmp_path)
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
        assert "project" in result.output.lower() or "capture" in result.output.lower()

    def test_help_in_chinese(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
        io = FakeIO()
        app = build_app(tmp_path, io)
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "自我进化" in result.output or "捕获" in result.output
