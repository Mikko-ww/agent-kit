"""测试 CLI 命令在子目录中的行为。"""

from pathlib import Path

import typer
from typer.testing import CliRunner

from self_evolve.config import SelfEvolveConfig, save_config
from self_evolve.plugin_cli import PluginRuntime, build_app
from self_evolve.storage import save_rule
from self_evolve.models import KnowledgeRule

import logging


runner = CliRunner()


def _make_runtime(cwd: Path) -> PluginRuntime:
    return PluginRuntime(
        logger=logging.getLogger("test"),
        cwd=cwd,
        config_root=cwd / ".config" / "agent-kit",
        data_root=cwd / ".local" / "share" / "agent-kit",
        cache_root=cwd / ".cache" / "agent-kit",
    )


def _init_project(root: Path) -> None:
    save_config(root, SelfEvolveConfig(language="en"))
    from self_evolve.config import rules_dir
    rules_dir(root).mkdir(parents=True, exist_ok=True)


def test_sync_from_subdirectory(tmp_path: Path):
    """从子目录运行 sync 应能找到项目根目录。"""
    _init_project(tmp_path)
    save_rule(tmp_path, KnowledgeRule(
        id="R-001", created_at="2026-01-01T00:00:00Z", status="active",
        title="T", statement="S", rationale="R", domain="testing", tags=[],
    ))
    # 创建 .git 目录使得 find_project_root 能定位
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "deep"
    subdir.mkdir(parents=True)

    app = build_app(cwd=subdir, runtime_factory=lambda: _make_runtime(subdir))
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "1" in result.stdout  # rules_count=1


def test_status_from_subdirectory(tmp_path: Path):
    """从子目录运行 status 应能找到项目根目录。"""
    _init_project(tmp_path)
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "deep"
    subdir.mkdir(parents=True)

    app = build_app(cwd=subdir, runtime_factory=lambda: _make_runtime(subdir))
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_init_uses_project_root_not_subdir(tmp_path: Path, monkeypatch):
    """从子目录运行 init 应在项目根目录初始化，而非子目录。"""
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "deep"
    subdir.mkdir(parents=True)
    monkeypatch.setenv("AGENT_KIT_LANG", "en")

    app = build_app(cwd=subdir, runtime_factory=lambda: _make_runtime(subdir))
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    # 配置应在 tmp_path（项目根目录），而非 subdir
    assert (tmp_path / ".agents" / "self-evolve" / "config.jsonc").exists()
    assert not (subdir / ".agents" / "self-evolve" / "config.jsonc").exists()


# ── status 增强测试 ──


def test_status_shows_domain_distribution(tmp_path: Path):
    """status 应展示 active 规则的 domain 分布。"""
    _init_project(tmp_path)
    save_rule(tmp_path, KnowledgeRule(
        id="R-001", created_at="2026-01-01T00:00:00Z", status="active",
        title="T", statement="S", rationale="R", domain="testing", tags=[],
    ))
    from self_evolve.sync import sync_skill
    sync_skill(tmp_path)

    app = build_app(cwd=tmp_path, runtime_factory=lambda: _make_runtime(tmp_path))
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "testing=1" in result.stdout


def test_status_shows_strategy_inline(tmp_path: Path):
    """少量规则时 status 应显示 inline 策略。"""
    _init_project(tmp_path)
    save_rule(tmp_path, KnowledgeRule(
        id="R-001", created_at="2026-01-01T00:00:00Z", status="active",
        title="T", statement="S", rationale="R", domain="testing", tags=[],
    ))

    app = build_app(cwd=tmp_path, runtime_factory=lambda: _make_runtime(tmp_path))
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "inline" in result.stdout


def test_status_shows_needs_sync_yes(tmp_path: Path):
    """先 sync 再添加新规则（不 sync），status 应显示需要同步。"""
    _init_project(tmp_path)
    save_rule(tmp_path, KnowledgeRule(
        id="R-001", created_at="2026-01-01T00:00:00Z", status="active",
        title="T", statement="S", rationale="R", domain="testing", tags=[],
    ))
    from self_evolve.sync import sync_skill
    sync_skill(tmp_path)

    import time
    time.sleep(0.05)

    save_rule(tmp_path, KnowledgeRule(
        id="R-002", created_at="2026-01-02T00:00:00Z", status="active",
        title="T2", statement="S2", rationale="R2", domain="testing", tags=[],
    ))

    app = build_app(cwd=tmp_path, runtime_factory=lambda: _make_runtime(tmp_path))
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "yes" in result.stdout.lower() or "是" in result.stdout


def test_status_shows_needs_sync_no(tmp_path: Path):
    """添加规则后 sync，status 应显示不需要同步。"""
    _init_project(tmp_path)
    save_rule(tmp_path, KnowledgeRule(
        id="R-001", created_at="2026-01-01T00:00:00Z", status="active",
        title="T", statement="S", rationale="R", domain="testing", tags=[],
    ))
    from self_evolve.sync import sync_skill
    sync_skill(tmp_path)

    app = build_app(cwd=tmp_path, runtime_factory=lambda: _make_runtime(tmp_path))
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "no" in result.stdout.lower() or "否" in result.stdout


def test_status_shows_last_synced(tmp_path: Path):
    """执行 sync 后 status 应展示当前日期。"""
    _init_project(tmp_path)
    save_rule(tmp_path, KnowledgeRule(
        id="R-001", created_at="2026-01-01T00:00:00Z", status="active",
        title="T", statement="S", rationale="R", domain="testing", tags=[],
    ))
    from self_evolve.sync import sync_skill
    sync_skill(tmp_path)

    app = build_app(cwd=tmp_path, runtime_factory=lambda: _make_runtime(tmp_path))
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "2026-" in result.stdout
