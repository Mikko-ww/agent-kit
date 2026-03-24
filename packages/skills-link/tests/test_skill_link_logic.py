from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


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


def test_save_and_load_config_round_trip(tmp_path: Path):
    config_module = require_module("skills_link.config")

    config = config_module.SkillLinkConfig(
        source_dir=tmp_path / "source",
        targets=[
            config_module.TargetConfig(name="codex", path=tmp_path / "codex"),
            config_module.TargetConfig(name="claude", path=tmp_path / "claude"),
        ],
    )
    config.source_dir.mkdir()
    for target in config.targets:
        target.path.mkdir()

    config_module.save_config(tmp_path / "config", config)
    loaded = config_module.load_config(tmp_path / "config")

    assert loaded == config
    assert config_module.config_file_path(tmp_path / "config").exists()
    assert '"config_version": 2' in config_module.config_file_path(tmp_path / "config").read_text(encoding="utf-8")


def test_load_config_rejects_legacy_single_target_schema(tmp_path: Path):
    config_module = require_module("skills_link.config")
    config_path = config_module.config_file_path(tmp_path / "config")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "plugin_id": "skills-link",
                "config_version": 1,
                "source_dir": str(tmp_path / "source"),
                "target_dir": str(tmp_path / "target"),
            }
        ),
        encoding="utf-8",
    )

    assert config_module.load_config(tmp_path / "config") is None


def test_discover_skill_statuses_reports_status_per_target(tmp_path: Path):
    config_module = require_module("skills_link.config")
    logic_module = require_module("skills_link.logic")

    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    source_dir.mkdir()
    codex_dir.mkdir()
    claude_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    write_skill(source_dir, "beta")
    write_skill(source_dir, "gamma")
    write_skill(source_dir, "delta")

    (codex_dir / "alpha").symlink_to(alpha, target_is_directory=True)
    (codex_dir / "beta").mkdir()
    (codex_dir / "gamma").symlink_to(tmp_path / "missing", target_is_directory=True)
    (claude_dir / "beta").symlink_to(source_dir / "beta", target_is_directory=True)

    config = config_module.SkillLinkConfig(
        source_dir=source_dir,
        targets=[
            config_module.TargetConfig(name="codex", path=codex_dir),
            config_module.TargetConfig(name="claude", path=claude_dir),
        ],
    )

    statuses = {
        item.name: {target.target_name: target.status for target in item.target_statuses}
        for item in logic_module.discover_skill_statuses(config)
    }

    assert statuses == {
        "alpha": {"codex": "linked", "claude": "not_linked"},
        "beta": {"codex": "conflict", "claude": "linked"},
        "gamma": {"codex": "broken_link", "claude": "not_linked"},
        "delta": {"codex": "not_linked", "claude": "not_linked"},
    }


def test_summarize_targets_reports_counts_per_target(tmp_path: Path):
    config_module = require_module("skills_link.config")
    logic_module = require_module("skills_link.logic")

    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    source_dir.mkdir()
    codex_dir.mkdir()
    claude_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    write_skill(source_dir, "beta")
    write_skill(source_dir, "gamma")

    (codex_dir / "alpha").symlink_to(alpha, target_is_directory=True)
    (codex_dir / "beta").mkdir()
    (claude_dir / "gamma").symlink_to(tmp_path / "missing", target_is_directory=True)

    config = config_module.SkillLinkConfig(
        source_dir=source_dir,
        targets=[
            config_module.TargetConfig(name="codex", path=codex_dir),
            config_module.TargetConfig(name="claude", path=claude_dir),
        ],
    )

    summaries = {item.name: item for item in logic_module.summarize_targets(config)}

    assert summaries["codex"].linked == 1
    assert summaries["codex"].conflict == 1
    assert summaries["codex"].not_linked == 1
    assert summaries["claude"].broken_link == 1
    assert summaries["claude"].not_linked == 2


def test_link_skills_creates_links_for_selected_targets_and_reports_conflicts(tmp_path: Path):
    config_module = require_module("skills_link.config")
    logic_module = require_module("skills_link.logic")

    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    source_dir.mkdir()
    codex_dir.mkdir()
    claude_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    write_skill(source_dir, "beta")
    (codex_dir / "beta").mkdir()

    config = config_module.SkillLinkConfig(
        source_dir=source_dir,
        targets=[
            config_module.TargetConfig(name="codex", path=codex_dir),
            config_module.TargetConfig(name="claude", path=claude_dir),
        ],
    )

    result = logic_module.link_skills(config, ["alpha", "beta"], target_names=["codex", "claude"])

    assert {(item.skill_name, item.target_name) for item in result.linked} == {
        ("alpha", "codex"),
        ("alpha", "claude"),
        ("beta", "claude"),
    }
    assert {(item.skill_name, item.target_name) for item in result.conflicts} == {
        ("beta", "codex"),
    }
    assert (codex_dir / "alpha").is_symlink()
    assert (codex_dir / "alpha").resolve() == alpha.resolve()
    assert (claude_dir / "alpha").is_symlink()
    assert (claude_dir / "alpha").resolve() == alpha.resolve()


def test_unlink_skills_only_removes_managed_links_from_selected_targets(tmp_path: Path):
    config_module = require_module("skills_link.config")
    logic_module = require_module("skills_link.logic")

    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    external_dir = tmp_path / "external"
    source_dir.mkdir()
    codex_dir.mkdir()
    claude_dir.mkdir()
    external_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    write_skill(source_dir, "foreign")
    (codex_dir / "alpha").symlink_to(alpha, target_is_directory=True)
    (claude_dir / "alpha").symlink_to(external_dir, target_is_directory=True)

    config = config_module.SkillLinkConfig(
        source_dir=source_dir,
        targets=[
            config_module.TargetConfig(name="codex", path=codex_dir),
            config_module.TargetConfig(name="claude", path=claude_dir),
        ],
    )

    result = logic_module.unlink_skills(config, ["alpha"], target_names=["codex", "claude"])

    assert {(item.skill_name, item.target_name) for item in result.unlinked} == {
        ("alpha", "codex"),
    }
    assert {(item.skill_name, item.target_name) for item in result.skipped} == {
        ("alpha", "claude"),
    }
    assert not (codex_dir / "alpha").exists()
    assert (claude_dir / "alpha").is_symlink()
