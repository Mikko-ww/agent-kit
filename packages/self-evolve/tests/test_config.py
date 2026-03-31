from pathlib import Path

from self_evolve.config import (
    SelfEvolveConfig,
    evolve_dir,
    find_project_root,
    load_config,
    rules_dir,
    save_config,
    skill_dir,
)


def test_path_helpers(tmp_path: Path):
    assert evolve_dir(tmp_path) == tmp_path / ".agents" / "self-evolve"
    assert rules_dir(tmp_path) == tmp_path / ".agents" / "self-evolve" / "rules"
    assert skill_dir(tmp_path) == tmp_path / ".agents" / "skills" / "self-evolve"


def test_save_and_load_config(tmp_path: Path):
    cfg = SelfEvolveConfig(language="zh-CN", inline_threshold=30)
    save_config(tmp_path, cfg)
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.language == "zh-CN"
    assert loaded.inline_threshold == 30


def test_load_config_returns_none_when_missing(tmp_path: Path):
    assert load_config(tmp_path) is None


def test_load_config_returns_none_for_wrong_version(tmp_path: Path):
    import json
    config_dir = tmp_path / ".agents" / "self-evolve"
    config_dir.mkdir(parents=True)
    (config_dir / "config.jsonc").write_text(
        json.dumps({"plugin_id": "self-evolve", "config_version": 4}),
        encoding="utf-8",
    )
    assert load_config(tmp_path) is None


def test_find_project_root_with_evolve_dir(tmp_path: Path):
    (tmp_path / ".agents" / "self-evolve").mkdir(parents=True)
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    found = find_project_root(sub)
    assert found == tmp_path


def test_find_project_root_returns_none(tmp_path: Path):
    sub = tmp_path / "empty"
    sub.mkdir()
    assert find_project_root(sub) is None
