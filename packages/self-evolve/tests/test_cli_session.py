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


def test_init_creates_v4_layout_and_empty_skill(tmp_path: Path):
    app = build_app(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert (tmp_path / ".agents" / "self-evolve" / "sessions").exists()
    assert (tmp_path / ".agents" / "self-evolve" / "candidates").exists()
    assert (tmp_path / ".agents" / "self-evolve" / "rules").exists()
    assert (tmp_path / ".agents" / "self-evolve" / "indexes").exists()
    assert (tmp_path / ".agents" / "skills" / "self-evolve" / "SKILL.md").exists()


def test_session_record_detect_and_status_flow(tmp_path: Path):
    app = build_app(tmp_path)
    runner.invoke(app, ["init"])

    result = runner.invoke(
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
            "--tag",
            "env",
        ],
    )
    assert result.exit_code == 0
    assert "S-" in result.output

    detect = runner.invoke(app, ["detect", "run"])
    assert detect.exit_code == 0
    assert "C-" in detect.output

    candidates = runner.invoke(app, ["candidate", "list"])
    assert candidates.exit_code == 0
    assert "Validate env before boot" in candidates.output

    status = runner.invoke(app, ["status"])
    assert status.exit_code == 0
    assert "sessions" in status.output.lower() or "会话" in status.output


def test_help_switches_with_language(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
    zh_app = build_app(tmp_path)
    zh_result = runner.invoke(zh_app, ["--help"])
    assert zh_result.exit_code == 0
    assert "自我进化" in zh_result.output or "会话" in zh_result.output

    monkeypatch.setenv("AGENT_KIT_LANG", "en")
    en_app = build_app(tmp_path)
    en_result = runner.invoke(en_app, ["--help"])
    assert en_result.exit_code == 0
    assert "session" in en_result.output.lower()
