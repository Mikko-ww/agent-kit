from __future__ import annotations

from pathlib import Path

import pytest

from self_evolve.config import (
    LegacyLayoutError,
    SelfEvolveConfig,
    candidates_dir,
    config_file_path,
    ensure_no_legacy_layout,
    indexes_dir,
    load_config,
    rules_dir,
    save_config,
    sessions_dir,
    skill_dir,
)
from self_evolve.jsonc import write_jsonc


def test_save_and_load_v4_config_round_trip(tmp_path: Path):
    config = SelfEvolveConfig(
        auto_accept_enabled=True,
        auto_accept_min_confidence=0.95,
        inline_threshold=42,
    )

    save_config(tmp_path, config)
    loaded = load_config(tmp_path)

    assert loaded == config


def test_load_config_rejects_legacy_config_version(tmp_path: Path):
    path = config_file_path(tmp_path)
    write_jsonc(
        path,
        {
            "plugin_id": "self-evolve",
            "config_version": 3,
            "promotion_threshold": 3,
        },
    )

    with pytest.raises(LegacyLayoutError):
        load_config(tmp_path)


def test_legacy_learning_layout_is_blocked(tmp_path: Path):
    (tmp_path / ".agents" / "self-evolve" / "learnings").mkdir(parents=True)

    with pytest.raises(LegacyLayoutError):
        ensure_no_legacy_layout(tmp_path)


def test_path_helpers_point_to_v4_layout(tmp_path: Path):
    assert config_file_path(tmp_path) == tmp_path / ".agents" / "self-evolve" / "config.jsonc"
    assert sessions_dir(tmp_path) == tmp_path / ".agents" / "self-evolve" / "sessions"
    assert candidates_dir(tmp_path) == tmp_path / ".agents" / "self-evolve" / "candidates"
    assert rules_dir(tmp_path) == tmp_path / ".agents" / "self-evolve" / "rules"
    assert indexes_dir(tmp_path) == tmp_path / ".agents" / "self-evolve" / "indexes"
    assert skill_dir(tmp_path) == tmp_path / ".agents" / "skills" / "self-evolve"
