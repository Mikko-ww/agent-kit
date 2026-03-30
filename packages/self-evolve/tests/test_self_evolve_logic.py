from __future__ import annotations

from pathlib import Path

import pytest


def test_init_creates_agent_directory_structure(tmp_path: Path):
    from self_evolve.logic import init_agent_dir, is_initialized

    assert not is_initialized(tmp_path)

    agent_dir = init_agent_dir(tmp_path)

    assert is_initialized(tmp_path)
    assert agent_dir == tmp_path / ".agent"
    assert (agent_dir / "memories").is_dir()
    assert (agent_dir / "skills").is_dir()
    assert (agent_dir / "skills" / "self-evolve" / "SKILL.md").is_file()


def test_capture_and_list_memories(tmp_path: Path):
    from self_evolve.config import ProjectConfig
    from self_evolve.logic import capture_memory, init_agent_dir, list_memories

    init_agent_dir(tmp_path)
    config = ProjectConfig(project_root=tmp_path)

    m1 = capture_memory(config, category="rule", subject="命名规范", content="使用 camelCase", source="审查")
    m2 = capture_memory(config, category="pattern", subject="错误处理", content="使用 try/except")
    m3 = capture_memory(config, category="learning", subject="性能", content="避免 N+1 查询")

    all_memories = list_memories(config)
    assert len(all_memories) == 3
    assert all_memories[0].id == m1.id
    assert all_memories[1].id == m2.id
    assert all_memories[2].id == m3.id

    rules = list_memories(config, category="rule")
    assert len(rules) == 1
    assert rules[0].subject == "命名规范"

    patterns = list_memories(config, category="pattern")
    assert len(patterns) == 1
    assert patterns[0].subject == "错误处理"

    learnings = list_memories(config, category="learning")
    assert len(learnings) == 1
    assert learnings[0].subject == "性能"


def test_get_memory(tmp_path: Path):
    from self_evolve.config import ProjectConfig
    from self_evolve.logic import capture_memory, get_memory, init_agent_dir

    init_agent_dir(tmp_path)
    config = ProjectConfig(project_root=tmp_path)

    captured = capture_memory(config, category="rule", subject="测试", content="内容", source="来源")

    found = get_memory(config, captured.id)
    assert found is not None
    assert found.id == captured.id
    assert found.category == "rule"
    assert found.subject == "测试"
    assert found.content == "内容"
    assert found.source == "来源"
    assert found.created_at != ""

    not_found = get_memory(config, "m-999")
    assert not_found is None


def test_validate_category_rejects_invalid():
    from self_evolve.logic import validate_category

    validate_category("rule")
    validate_category("pattern")
    validate_category("learning")

    with pytest.raises(ValueError, match="invalid category"):
        validate_category("invalid")


def test_list_and_get_skills(tmp_path: Path):
    from self_evolve.config import ProjectConfig
    from self_evolve.logic import get_skill, init_agent_dir, list_skills

    init_agent_dir(tmp_path)
    config = ProjectConfig(project_root=tmp_path)

    skills = list_skills(config)
    assert len(skills) == 1
    assert skills[0].name == "self-evolve"
    assert skills[0].description != ""

    skill = get_skill(config, "self-evolve")
    assert skill is not None
    assert skill.name == "self-evolve"

    not_found = get_skill(config, "nonexistent")
    assert not_found is None


def test_get_status(tmp_path: Path):
    from self_evolve.config import ProjectConfig
    from self_evolve.logic import capture_memory, get_status, init_agent_dir

    init_agent_dir(tmp_path)
    config = ProjectConfig(project_root=tmp_path)

    capture_memory(config, category="rule", subject="r1", content="c1")
    capture_memory(config, category="rule", subject="r2", content="c2")
    capture_memory(config, category="pattern", subject="p1", content="c3")
    capture_memory(config, category="learning", subject="l1", content="c4")

    summary = get_status(config)
    assert summary.project_root == tmp_path
    assert summary.total_memories == 4
    assert summary.rules == 2
    assert summary.patterns == 1
    assert summary.learnings == 1
    assert summary.skills == 1


def test_memory_id_increments(tmp_path: Path):
    from self_evolve.config import ProjectConfig
    from self_evolve.logic import capture_memory, init_agent_dir

    init_agent_dir(tmp_path)
    config = ProjectConfig(project_root=tmp_path)

    m1 = capture_memory(config, category="rule", subject="a", content="b")
    m2 = capture_memory(config, category="rule", subject="c", content="d")
    m3 = capture_memory(config, category="rule", subject="e", content="f")

    assert m1.id == "m-001"
    assert m2.id == "m-002"
    assert m3.id == "m-003"


def test_custom_skills_discovered(tmp_path: Path):
    from self_evolve.config import ProjectConfig
    from self_evolve.logic import init_agent_dir, list_skills

    init_agent_dir(tmp_path)
    config = ProjectConfig(project_root=tmp_path)

    # 添加自定义技能
    custom_skill = config.skills_dir / "my-skill"
    custom_skill.mkdir()
    (custom_skill / "SKILL.md").write_text("# my-skill\n\n自定义技能描述。\n", encoding="utf-8")

    skills = list_skills(config)
    assert len(skills) == 2
    names = [s.name for s in skills]
    assert "self-evolve" in names
    assert "my-skill" in names
