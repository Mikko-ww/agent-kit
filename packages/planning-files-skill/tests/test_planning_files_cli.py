from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def build_app(tmp_path: Path):
    plugin_cli = require_module("planning_files_skill.plugin_cli")
    runtime = SimpleNamespace(
        logger=logging.getLogger("planning-files-skill-test"),
        cwd=tmp_path / "repo",
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
        home_dir=tmp_path / "home",
    )
    runtime.cwd.mkdir(parents=True)
    runtime.home_dir.mkdir(parents=True)
    return plugin_cli.build_app(runtime_factory=lambda: runtime), runtime


def test_plugin_metadata_output():
    plugin_cli = require_module("planning_files_skill.plugin_cli")
    result = CliRunner().invoke(plugin_cli.build_app(), ["--plugin-metadata"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["plugin_id"] == "planning-files-skill"
    assert payload["config_version"] == 1


def test_help_uses_zh_cn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
    app, _ = build_app(tmp_path)

    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "导入 planning-files skill" in result.output
    assert "导入平台资源" in result.output


def test_import_dry_run_does_not_write_files(tmp_path: Path):
    app, runtime = build_app(tmp_path)

    result = CliRunner().invoke(
        app,
        ["import", "--platform", "generic", "--language", "en", "--scope", "project", "--dry-run"],
    )

    assert result.exit_code == 0
    assert "would_write" in result.output
    assert not (runtime.cwd / ".agents" / "skills" / "planning-files").exists()


def test_import_rejects_unsupported_language_without_traceback(tmp_path: Path):
    app, _ = build_app(tmp_path)

    result = CliRunner().invoke(
        app,
        ["import", "--platform", "generic", "--language", "fr", "--scope", "project"],
    )

    assert result.exit_code == 1
    assert "unsupported language: fr" in result.stderr
    assert result.exception is None or not isinstance(result.exception, RuntimeError)


def test_import_and_status_report_installed_skill(tmp_path: Path):
    app, runtime = build_app(tmp_path)
    runner = CliRunner()

    import_result = runner.invoke(
        app,
        ["import", "--platform", "generic", "--language", "zh-CN", "--scope", "project"],
    )
    status_result = runner.invoke(app, ["status", "--platform", "generic", "--scope", "project"])

    assert import_result.exit_code == 0
    assert "generic project" in import_result.output
    assert status_result.exit_code == 0
    assert "installed" in status_result.output
    assert "zh-CN" in status_result.output
    assert (runtime.cwd / ".agents" / "skills" / "planning-files" / "SKILL.md").exists()
