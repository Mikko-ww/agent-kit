from __future__ import annotations

import importlib
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"could not import {name}: {exc}")


def build_app(tmp_path: Path, *, cwd: Path | None = None):
    plugin_cli = require_module("self_evolve.plugin_cli")
    runtime = SimpleNamespace(
        logger=logging.getLogger("self-evolve-test"),
        cwd=cwd or tmp_path,
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
    )
    return plugin_cli.build_app(runtime_factory=lambda: runtime)


def test_plugin_metadata_output():
    plugin_cli = require_module("self_evolve.plugin_cli")
    result = CliRunner().invoke(plugin_cli.build_app(), ["--plugin-metadata"])

    assert result.exit_code == 0
    assert '"plugin_id": "self-evolve"' in result.output
    assert '"config_version": 1' in result.output


def test_init_creates_agent_dir(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert ".agents" in result.output
    assert (tmp_path / ".agents" / "memories").is_dir()
    assert (tmp_path / ".agents" / "skills" / "self-evolve" / "SKILL.md").is_file()


def test_init_skips_when_already_initialized(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "already exists" in result.output or "已存在" in result.output


def test_capture_and_list_and_show(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])

    capture_result = runner.invoke(app, [
        "capture",
        "--category", "rule",
        "--subject", "test-subject",
        "--content", "test-content",
        "--source", "test-source",
    ])
    assert capture_result.exit_code == 0
    assert "m-001" in capture_result.output
    assert "rule" in capture_result.output

    list_result = runner.invoke(app, ["list"])
    assert list_result.exit_code == 0
    assert "m-001" in list_result.output
    assert "test-subject" in list_result.output

    show_result = runner.invoke(app, ["show", "m-001"])
    assert show_result.exit_code == 0
    assert "test-subject" in show_result.output
    assert "test-content" in show_result.output
    assert "test-source" in show_result.output


def test_list_filters_by_category(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    runner.invoke(app, ["capture", "--category", "rule", "--subject", "r1", "--content", "c1"])
    runner.invoke(app, ["capture", "--category", "pattern", "--subject", "p1", "--content", "c2"])

    all_result = runner.invoke(app, ["list"])
    assert all_result.exit_code == 0
    assert "r1" in all_result.output
    assert "p1" in all_result.output

    filtered = runner.invoke(app, ["list", "--category", "rule"])
    assert filtered.exit_code == 0
    assert "r1" in filtered.output
    assert "p1" not in filtered.output


def test_list_empty_shows_no_memories(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No memories" in result.output or "未找到" in result.output


def test_show_missing_memory_exits_with_error(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["show", "m-999"])

    assert result.exit_code == 1


def test_capture_invalid_category_exits_with_error(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    result = runner.invoke(app, [
        "capture",
        "--category", "invalid",
        "--subject", "s",
        "--content", "c",
    ])

    assert result.exit_code == 1


def test_status_command(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    runner.invoke(app, ["capture", "--category", "rule", "--subject", "r1", "--content", "c1"])
    runner.invoke(app, ["capture", "--category", "pattern", "--subject", "p1", "--content", "c2"])

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "memories: 2" in result.output
    assert "rules: 1" in result.output
    assert "patterns: 1" in result.output
    assert "skills: 1" in result.output


def test_skill_list_command(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "list"])

    assert result.exit_code == 0
    assert "self-evolve" in result.output


def test_skill_show_command(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "show", "self-evolve"])

    assert result.exit_code == 0
    assert "self-evolve" in result.output


def test_skill_show_not_found_exits_with_error(tmp_path: Path):
    app = build_app(tmp_path)
    runner = CliRunner()

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "show", "nonexistent"])

    assert result.exit_code == 1


def test_commands_fail_without_init(tmp_path: Path):
    project_dir = tmp_path / "no-init"
    project_dir.mkdir()
    app = build_app(tmp_path, cwd=project_dir)
    runner = CliRunner()

    for cmd in [
        ["list"],
        ["status"],
        ["show", "m-001"],
        ["capture", "--category", "rule", "--subject", "s", "--content", "c"],
        ["skill", "list"],
        ["skill", "show", "self-evolve"],
    ]:
        result = runner.invoke(app, cmd)
        assert result.exit_code == 1, f"expected exit 1 for: {cmd}"


def test_help_uses_zh_cn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
    app = build_app(tmp_path)
    runner = CliRunner()

    root_help = runner.invoke(app, ["--help"])
    skill_help = runner.invoke(app, ["skill", "--help"])

    assert root_help.exit_code == 0
    assert "项目级自我进化工具。" in root_help.output
    assert skill_help.exit_code == 0
    assert "管理 .agents 目录中的技能。" in skill_help.output
