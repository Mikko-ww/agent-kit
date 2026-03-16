from __future__ import annotations

import importlib
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
    config_module = require_module("agent_kit_skill_link.config")

    config = config_module.SkillLinkConfig(
        source_dir=tmp_path / "source",
        target_dir=tmp_path / "target",
    )
    config.source_dir.mkdir()
    config.target_dir.mkdir()

    config_module.save_config(tmp_path, config)
    loaded = config_module.load_config(tmp_path)

    assert loaded == config
    assert config_module.config_file_path(tmp_path).exists()


def test_discover_skill_statuses_reports_linked_conflict_broken_and_unlinked(tmp_path: Path):
    config_module = require_module("agent_kit_skill_link.config")
    logic_module = require_module("agent_kit_skill_link.logic")

    source_dir = tmp_path / "skills"
    target_dir = tmp_path / "linked"
    source_dir.mkdir()
    target_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    write_skill(source_dir, "beta")
    write_skill(source_dir, "gamma")
    write_skill(source_dir, "delta")

    (target_dir / "alpha").symlink_to(alpha, target_is_directory=True)
    (target_dir / "beta").mkdir()
    (target_dir / "gamma").symlink_to(tmp_path / "missing", target_is_directory=True)

    config = config_module.SkillLinkConfig(source_dir=source_dir, target_dir=target_dir)

    statuses = {
        item.name: item.status for item in logic_module.discover_skill_statuses(config)
    }

    assert statuses == {
        "alpha": "linked",
        "beta": "conflict",
        "gamma": "broken_link",
        "delta": "not_linked",
    }


def test_link_skills_creates_links_and_reports_conflicts(tmp_path: Path):
    config_module = require_module("agent_kit_skill_link.config")
    logic_module = require_module("agent_kit_skill_link.logic")

    source_dir = tmp_path / "skills"
    target_dir = tmp_path / "linked"
    source_dir.mkdir()
    target_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    write_skill(source_dir, "beta")
    (target_dir / "beta").mkdir()

    config = config_module.SkillLinkConfig(source_dir=source_dir, target_dir=target_dir)

    result = logic_module.link_skills(config, ["alpha", "beta"])

    assert result.linked == ["alpha"]
    assert result.conflicts == ["beta"]
    assert (target_dir / "alpha").is_symlink()
    assert (target_dir / "alpha").resolve() == alpha.resolve()


def test_unlink_skills_only_removes_symlinks_pointing_to_source_dir(tmp_path: Path):
    config_module = require_module("agent_kit_skill_link.config")
    logic_module = require_module("agent_kit_skill_link.logic")

    source_dir = tmp_path / "skills"
    target_dir = tmp_path / "linked"
    external_dir = tmp_path / "external"
    source_dir.mkdir()
    target_dir.mkdir()
    external_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    write_skill(source_dir, "foreign")
    (target_dir / "alpha").symlink_to(alpha, target_is_directory=True)
    (target_dir / "foreign").symlink_to(external_dir, target_is_directory=True)

    config = config_module.SkillLinkConfig(source_dir=source_dir, target_dir=target_dir)

    result = logic_module.unlink_skills(config, ["alpha", "foreign"])

    assert result.unlinked == ["alpha"]
    assert result.skipped == ["foreign"]
    assert not (target_dir / "alpha").exists()
    assert (target_dir / "foreign").is_symlink()
