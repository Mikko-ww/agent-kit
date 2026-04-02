import json
from pathlib import Path

from self_evolve.config import SelfEvolveConfig, save_config
from self_evolve.models import KnowledgeRule
from self_evolve.storage import save_rule
from self_evolve.sync import sync_skill


def _init_project(tmp_path: Path, language: str = "en") -> None:
    save_config(tmp_path, SelfEvolveConfig(language=language))


def _make_rule(
    rule_id: str = "R-001",
    domain: str = "testing",
    status: str = "active",
) -> KnowledgeRule:
    return KnowledgeRule(
        id=rule_id,
        created_at="2026-03-31T12:00:00Z",
        status=status,
        title=f"Rule {rule_id}",
        statement="Test statement.",
        rationale="Test rationale.",
        domain=domain,
        tags=["ci"],
    )


def test_sync_generates_skill_md(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    assert result.path.exists()
    assert result.rules_count == 1
    assert result.strategy == "inline"
    content = result.path.read_text(encoding="utf-8")
    assert "R-001" in content


def test_sync_generates_catalog_v1(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    assert result.catalog_path is not None
    catalog = json.loads(result.catalog_path.read_text(encoding="utf-8"))
    assert catalog["version"] == 1
    assert catalog["summary"]["total_rules"] == 1
    assert len(catalog["rules"]) == 1
    rule_entry = catalog["rules"][0]
    assert "source_sessions" not in rule_entry
    assert "source_candidates" not in rule_entry


def test_sync_only_includes_active_rules(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule("R-001", status="active"))
    save_rule(tmp_path, _make_rule("R-002", status="retired"))
    result = sync_skill(tmp_path)
    assert result.rules_count == 1


def test_sync_index_strategy(tmp_path: Path):
    _init_project(tmp_path)
    for i in range(25):
        save_rule(tmp_path, _make_rule(f"R-{i + 1:03d}"))
    result = sync_skill(tmp_path, inline_threshold=20)
    assert result.strategy == "index"
    assert len(result.domain_files) > 0


def test_sync_copies_all_scripts(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    script_names = {p.name for p in result.script_paths}
    assert "find_rules.py" in script_names
    assert "add_rule.py" in script_names
    assert "edit_rule.py" in script_names
    assert "retire_rule.py" in script_names
    assert "list_rules.py" in script_names


def test_sync_empty_project(tmp_path: Path):
    _init_project(tmp_path)
    result = sync_skill(tmp_path)
    assert result.rules_count == 0
    assert result.strategy == "inline"


def test_sync_uses_zh_cn_template(tmp_path: Path):
    _init_project(tmp_path, language="zh-CN")
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    content = result.path.read_text(encoding="utf-8")
    assert "项目知识规则" in content or "规则" in content


def test_sync_falls_back_to_agent_kit_lang(tmp_path: Path, monkeypatch):
    save_config(tmp_path, SelfEvolveConfig(language=None))
    monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    assert result.path.exists()


def test_sync_index_mixed_timestamp_formats(tmp_path: Path):
    """时间戳使用不同 ISO 格式（Z 和 +00:00）时应正确解析比较。"""
    _init_project(tmp_path)
    rule_z = _make_rule("R-001")
    rule_z.created_at = "2026-03-01T12:00:00Z"
    save_rule(tmp_path, rule_z)

    rule_offset = _make_rule("R-002")
    rule_offset.created_at = "2026-03-15T12:00:00+00:00"
    save_rule(tmp_path, rule_offset)

    for i in range(23):
        r = _make_rule(f"R-{i + 3:03d}")
        r.created_at = f"2026-01-{i + 1:02d}T00:00:00Z"
        save_rule(tmp_path, r)

    result = sync_skill(tmp_path, inline_threshold=20)
    assert result.strategy == "index"
    content = result.path.read_text(encoding="utf-8")
    assert "2026-03-15" in content


def test_sync_index_unsafe_domain_uses_safe_filenames(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule("R-001", domain="Debugging / Tips"))

    result = sync_skill(tmp_path, inline_threshold=0)

    assert result.strategy == "index"
    assert len(result.domain_files) == 1
    domain_file = result.domain_files[0]
    assert domain_file.parent.name == "domains"
    assert domain_file.exists()
    assert domain_file.name == "debugging-tips.md"
    assert " " not in domain_file.name
    assert "/" not in domain_file.name

    skill_content = result.path.read_text(encoding="utf-8")
    assert "[→ details](domains/debugging-tips.md)" in skill_content
    assert "Debugging / Tips" in skill_content

    detail_content = domain_file.read_text(encoding="utf-8")
    assert "Debugging / Tips" in detail_content


def test_sync_index_domain_slug_conflict_adds_hash_suffix(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule("R-001", domain="A/B"))
    save_rule(tmp_path, _make_rule("R-002", domain="A B"))

    result = sync_skill(tmp_path, inline_threshold=0)

    assert result.strategy == "index"
    domain_names = sorted(path.name for path in result.domain_files)
    assert len(domain_names) == 2
    assert domain_names[0] != domain_names[1]
    assert all(name.startswith("a-b--") and name.endswith(".md") for name in domain_names)

    skill_content = result.path.read_text(encoding="utf-8")
    for domain_name in domain_names:
        assert f"(domains/{domain_name})" in skill_content
    assert skill_content.count("[→ details](") == 2


def test_sync_index_reserved_windows_name_adds_hash_suffix(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule("R-001", domain="CON"))

    result = sync_skill(tmp_path, inline_threshold=0)

    assert result.strategy == "index"
    assert len(result.domain_files) == 1
    domain_file = result.domain_files[0]
    assert domain_file.name.startswith("con--")
    assert domain_file.name.endswith(".md")

    skill_content = result.path.read_text(encoding="utf-8")
    assert f"(domains/{domain_file.name})" in skill_content


def test_sync_index_stale_safe_domain_files_are_removed(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule("R-001", domain="Debugging / Tips"))

    first_result = sync_skill(tmp_path, inline_threshold=0)
    old_domain_file = first_result.domain_files[0]
    assert old_domain_file.exists()

    save_rule(tmp_path, _make_rule("R-001", domain="Release / Notes"))

    second_result = sync_skill(tmp_path, inline_threshold=0)

    assert not old_domain_file.exists()
    assert len(second_result.domain_files) == 1
    assert second_result.domain_files[0].name == "release-notes.md"
    assert second_result.domain_files[0].exists()
