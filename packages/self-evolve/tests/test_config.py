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


# ── JSONC round-trip 测试 ──


def test_save_config_new_file_has_header_comment(tmp_path: Path):
    """新建配置文件应包含 header comment。"""
    save_config(tmp_path, SelfEvolveConfig(language="en"))
    from self_evolve.config import config_file_path
    content = config_file_path(tmp_path).read_text(encoding="utf-8")
    assert content.startswith("//")
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.language == "en"


def test_save_config_preserves_preamble_comments(tmp_path: Path):
    """写回配置时应保留文件头部注释。"""
    from self_evolve.config import config_file_path
    save_config(tmp_path, SelfEvolveConfig(language="en"))
    path = config_file_path(tmp_path)
    original = path.read_text(encoding="utf-8")
    commented = "// My custom preamble\n// Second line\n" + original
    path.write_text(commented, encoding="utf-8")
    save_config(tmp_path, SelfEvolveConfig(language="zh-CN"))
    updated = path.read_text(encoding="utf-8")
    assert "// My custom preamble" in updated
    assert "// Second line" in updated
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.language == "zh-CN"


def test_save_config_preserves_inline_comments(tmp_path: Path):
    """写回配置时应保留行内注释。"""
    from self_evolve.config import config_file_path
    save_config(tmp_path, SelfEvolveConfig(language="en"))
    path = config_file_path(tmp_path)
    content = path.read_text(encoding="utf-8")
    content = content.replace('"language": "en"', '"language": "en"  // template lang')
    path.write_text(content, encoding="utf-8")
    save_config(tmp_path, SelfEvolveConfig(language="zh-CN", inline_threshold=50))
    updated = path.read_text(encoding="utf-8")
    assert "// template lang" in updated
    assert '"zh-CN"' in updated
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.language == "zh-CN"
    assert loaded.inline_threshold == 50


def test_save_config_preserves_interleaved_comments(tmp_path: Path):
    """写回配置时应保留字段间的注释块。"""
    from self_evolve.config import config_file_path
    save_config(tmp_path, SelfEvolveConfig(language="en"))
    path = config_file_path(tmp_path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        '  "language"',
        '  // Language setting for templates\n  "language"',
    )
    path.write_text(content, encoding="utf-8")
    save_config(tmp_path, SelfEvolveConfig(language="zh-CN"))
    updated = path.read_text(encoding="utf-8")
    assert "// Language setting for templates" in updated
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.language == "zh-CN"


def test_save_config_round_trip_values_correct(tmp_path: Path):
    """完整 round-trip：保存→手工加注释→修改值→保存→读取应正确。"""
    from self_evolve.config import config_file_path
    save_config(tmp_path, SelfEvolveConfig(language="en", inline_threshold=20))
    path = config_file_path(tmp_path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        '"inline_threshold": 20',
        '"inline_threshold": 20  // default is 20',
    )
    path.write_text(content, encoding="utf-8")
    save_config(tmp_path, SelfEvolveConfig(language="zh-CN", inline_threshold=30))
    updated = path.read_text(encoding="utf-8")
    assert "// default is 20" in updated
    assert "30" in updated
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.language == "zh-CN"
    assert loaded.inline_threshold == 30


def test_merge_flat_jsonc_basic():
    """merge_flat_jsonc 应正确替换值并保留注释。"""
    from self_evolve.jsonc import merge_flat_jsonc, loads_jsonc
    raw = '''{
  "name": "old",  // keep this
  // a comment
  "count": 10
}
'''
    result = merge_flat_jsonc(raw, {"name": "new", "count": 42})
    assert '"new"' in result
    assert "42" in result
    assert "// keep this" in result
    assert "// a comment" in result
    data = loads_jsonc(result)
    assert data["name"] == "new"
    assert data["count"] == 42


def test_merge_flat_jsonc_null_value():
    """merge_flat_jsonc 应正确处理 null 值。"""
    from self_evolve.jsonc import merge_flat_jsonc
    raw = '{\n  "lang": null\n}\n'
    result = merge_flat_jsonc(raw, {"lang": "en"})
    assert '"en"' in result
    assert "null" not in result
