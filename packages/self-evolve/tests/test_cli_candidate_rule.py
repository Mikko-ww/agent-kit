from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner


runner = CliRunner()


def build_app(tmp_path: Path):
    from self_evolve.plugin_cli import build_app

    runtime = SimpleNamespace(
        logger=logging.getLogger("self-evolve-test"),
        cwd=tmp_path,
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
    )
    return build_app(runtime_factory=lambda: runtime)


def test_candidate_accept_then_sync(tmp_path: Path):
    app = build_app(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(
        app,
        [
            "session",
            "record",
            "--summary",
            "Fix startup validation",
            "--domain",
            "debugging",
            "--outcome",
            "success",
            "--lesson",
            "Validate env before boot",
        ],
    )
    runner.invoke(app, ["detect", "run"])

    accepted = runner.invoke(app, ["candidate", "accept", "C-001"])
    assert accepted.exit_code == 0
    assert "R-001" in accepted.output

    listed = runner.invoke(app, ["rule", "list"])
    assert listed.exit_code == 0
    assert "Validate env before boot" in listed.output

    synced = runner.invoke(app, ["sync"])
    assert synced.exit_code == 0
    assert "SKILL.md" in synced.output


def test_rule_add_and_retire(tmp_path: Path):
    app = build_app(tmp_path)
    runner.invoke(app, ["init"])

    added = runner.invoke(
        app,
        [
            "rule",
            "add",
            "--title",
            "Validate env before boot",
            "--statement",
            "Validate required environment variables before booting the service.",
            "--rationale",
            "Prevents partial startup failure.",
            "--domain",
            "debugging",
            "--tag",
            "env",
        ],
    )
    assert added.exit_code == 0
    assert "R-001" in added.output

    retired = runner.invoke(app, ["rule", "retire", "R-001"])
    assert retired.exit_code == 0
    assert "retired" in retired.output.lower() or "停用" in retired.output


def test_init_rejects_legacy_layout(tmp_path: Path):
    (tmp_path / ".agents" / "self-evolve" / "learnings").mkdir(parents=True)
    app = build_app(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "legacy" in result.output.lower() or "旧格式" in result.output
