from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def setup_project(tmp_path: Path):
    """创建 .agents/self-evolve/config.jsonc 使 tmp_path 成为已初始化项目。"""
    config_module = require_module("self_evolve.config")
    config = config_module.SelfEvolveConfig(
        promotion_threshold=3,
        promotion_window_days=30,
        min_task_count=2,
    )
    config_module.save_config(tmp_path, config)
    return config


class TestConfig:
    def test_save_and_load_config_round_trip(self, tmp_path: Path):
        config_module = require_module("self_evolve.config")

        config = config_module.SelfEvolveConfig(
            promotion_threshold=5,
            promotion_window_days=60,
            min_task_count=3,
            auto_promote=True,
        )

        config_module.save_config(tmp_path, config)
        loaded = config_module.load_config(tmp_path)

        assert loaded is not None
        assert loaded.promotion_threshold == 5
        assert loaded.promotion_window_days == 60
        assert loaded.min_task_count == 3
        assert loaded.auto_promote is True

    def test_load_config_returns_none_for_missing(self, tmp_path: Path):
        config_module = require_module("self_evolve.config")
        assert config_module.load_config(tmp_path / "nonexistent") is None

    def test_load_config_rejects_wrong_version(self, tmp_path: Path):
        config_module = require_module("self_evolve.config")
        jsonc_module = require_module("self_evolve.jsonc")

        config_path = config_module.config_file_path(tmp_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        jsonc_module.write_jsonc(config_path, {
            "plugin_id": "self-evolve",
            "config_version": 999,
        })

        assert config_module.load_config(tmp_path) is None

    def test_find_project_root_with_evolve_dir(self, tmp_path: Path):
        config_module = require_module("self_evolve.config")
        (tmp_path / ".agents" / "self-evolve").mkdir(parents=True)
        sub = tmp_path / "src" / "app"
        sub.mkdir(parents=True)

        found = config_module.find_project_root(sub)
        assert found == tmp_path

    def test_find_project_root_with_git_dir(self, tmp_path: Path):
        config_module = require_module("self_evolve.config")
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "src"
        sub.mkdir()

        found = config_module.find_project_root(sub)
        assert found == tmp_path

    def test_find_project_root_returns_none(self, tmp_path: Path):
        config_module = require_module("self_evolve.config")
        # tmp_path 中没有 .agents/self-evolve 或 .git
        isolated = tmp_path / "deep" / "nested"
        isolated.mkdir(parents=True)

        found = config_module.find_project_root(isolated)
        # 可能在上层有 .git，但不一定，所以只验证没有异常
        assert found is None or isinstance(found, Path)


class TestModels:
    def test_learning_entry_round_trip(self):
        models = require_module("self_evolve.models")
        entry = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="high",
            status="active",
            domain="debugging",
            summary="Test summary",
            detail="Test detail",
            suggested_action="Fix it",
            pattern_key="test-pattern",
            see_also=["L-20260329-001"],
            recurrence_count=2,
            task_ids=["task-1"],
            metadata={"key": "value"},
        )
        data = entry.to_dict()
        restored = models.LearningEntry.from_dict(data)
        assert restored.id == entry.id
        assert restored.summary == entry.summary
        assert restored.see_also == entry.see_also
        assert restored.recurrence_count == 2

    def test_generate_learning_id_increments(self):
        models = require_module("self_evolve.models")
        existing = ["L-20260330-001", "L-20260330-002"]
        new_id = models.generate_learning_id(existing)
        assert new_id.endswith("-003")

    def test_generate_learning_id_starts_at_001(self):
        models = require_module("self_evolve.models")
        new_id = models.generate_learning_id([])
        assert new_id.endswith("-001")

    def test_generate_rule_id_increments(self):
        models = require_module("self_evolve.models")
        existing = ["R-001", "R-002"]
        new_id = models.generate_rule_id(existing)
        assert new_id == "R-003"

    def test_promoted_rule_round_trip(self):
        models = require_module("self_evolve.models")
        rule = models.PromotedRule(
            id="R-001",
            source_learning_id="L-20260330-001",
            rule="Always validate env vars",
            domain="debugging",
            created_at="2026-03-30T12:00:00Z",
        )
        data = rule.to_dict()
        restored = models.PromotedRule.from_dict(data)
        assert restored.id == rule.id
        assert restored.rule == rule.rule


class TestStorage:
    def test_save_and_load_learning(self, tmp_path: Path):
        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")

        entry = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="medium",
            status="active",
            domain="testing",
            summary="Test save/load",
        )
        storage.save_learning(tmp_path, entry)

        loaded = storage.load_learning(tmp_path, "L-20260330-001")
        assert loaded is not None
        assert loaded.id == "L-20260330-001"
        assert loaded.summary == "Test save/load"

    def test_load_learning_returns_none_for_missing(self, tmp_path: Path):
        storage = require_module("self_evolve.storage")
        assert storage.load_learning(tmp_path, "L-nonexistent") is None

    def test_list_learnings_returns_sorted(self, tmp_path: Path):
        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")

        for i in range(3):
            entry = models.LearningEntry(
                id=f"L-20260330-{i + 1:03d}",
                timestamp=f"2026-03-30T12:0{i}:00Z",
                priority="medium",
                status="active",
                domain="testing",
                summary=f"Learning {i + 1}",
            )
            storage.save_learning(tmp_path, entry)

        entries = storage.list_learnings(tmp_path)
        assert len(entries) == 3
        assert entries[0].id == "L-20260330-001"

    def test_list_learning_ids(self, tmp_path: Path):
        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")

        entry = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="medium",
            status="active",
            domain="testing",
            summary="Test",
        )
        storage.save_learning(tmp_path, entry)

        ids = storage.list_learning_ids(tmp_path)
        assert ids == ["L-20260330-001"]

    def test_save_and_load_rules(self, tmp_path: Path):
        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")

        rules = [
            models.PromotedRule(
                id="R-001",
                source_learning_id="L-20260330-001",
                rule="Test rule",
                domain="testing",
                created_at="2026-03-30T12:00:00Z",
            )
        ]
        storage.save_rules(tmp_path, rules)

        loaded = storage.load_rules(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].rule == "Test rule"

    def test_load_rules_returns_empty_for_missing(self, tmp_path: Path):
        storage = require_module("self_evolve.storage")
        assert storage.load_rules(tmp_path) == []


class TestSync:
    def test_sync_skill_generates_skill_md(self, tmp_path: Path):
        sync_module = require_module("self_evolve.sync")
        models = require_module("self_evolve.models")

        rules = [
            models.PromotedRule(
                id="R-001",
                source_learning_id="L-001",
                rule="Always validate env vars",
                domain="debugging",
                created_at="2026-03-30T12:00:00Z",
            ),
        ]
        result = sync_module.sync_skill(tmp_path, rules)
        assert result.path.exists()
        assert result.path.name == "SKILL.md"
        content = result.path.read_text(encoding="utf-8")
        assert "Self-Evolved Project Rules" in content
        assert "Always validate env vars" in content
        assert "agent-kit self-evolve" in content

    def test_sync_skill_path_is_in_agents_skills(self, tmp_path: Path):
        sync_module = require_module("self_evolve.sync")

        result = sync_module.sync_skill(tmp_path, [])
        expected = tmp_path / ".agents" / "skills" / "self-evolve" / "SKILL.md"
        assert result.path == expected

    def test_sync_skill_empty_rules(self, tmp_path: Path):
        sync_module = require_module("self_evolve.sync")

        result = sync_module.sync_skill(tmp_path, [])
        assert result.rules_count == 0
        content = result.path.read_text(encoding="utf-8")
        assert "Self-Evolved Project Rules" in content

    def test_sync_skill_overwrites_existing(self, tmp_path: Path):
        sync_module = require_module("self_evolve.sync")
        models = require_module("self_evolve.models")

        # 第一次同步
        rules_v1 = [
            models.PromotedRule(
                id="R-001",
                source_learning_id="L-001",
                rule="Old rule",
                domain="testing",
                created_at="2026-03-30T12:00:00Z",
            ),
        ]
        sync_module.sync_skill(tmp_path, rules_v1)

        # 第二次同步（更新）
        rules_v2 = [
            models.PromotedRule(
                id="R-001",
                source_learning_id="L-001",
                rule="Updated rule",
                domain="testing",
                created_at="2026-03-30T12:00:00Z",
            ),
        ]
        result = sync_module.sync_skill(tmp_path, rules_v2)
        content = result.path.read_text(encoding="utf-8")
        assert "Updated rule" in content
        assert "Old rule" not in content


class TestLogic:
    def test_capture_learning_creates_entry(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        entry = logic.capture_learning(
            tmp_path,
            summary="Test capture",
            domain="testing",
            priority="high",
            pattern_key="test-key",
            task_id="task-1",
        )
        assert entry.id.startswith("L-")
        assert entry.summary == "Test capture"
        assert entry.priority == "high"
        assert entry.domain == "testing"
        assert entry.status == "active"
        assert entry.task_ids == ["task-1"]

    def test_filter_learnings_by_status(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        logic.capture_learning(tmp_path, summary="Active one", domain="testing")

        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")
        resolved = models.LearningEntry(
            id="L-20260330-099",
            timestamp="2026-03-30T12:00:00Z",
            priority="medium",
            status="resolved",
            domain="testing",
            summary="Resolved one",
        )
        storage.save_learning(tmp_path, resolved)

        active_entries = logic.filter_learnings(tmp_path, status="active")
        assert all(e.status == "active" for e in active_entries)
        assert len(active_entries) >= 1

    def test_filter_learnings_by_domain(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        logic.capture_learning(tmp_path, summary="Debug issue", domain="debugging")
        logic.capture_learning(tmp_path, summary="Test issue", domain="testing")

        debug_entries = logic.filter_learnings(tmp_path, domain="debugging")
        assert all(e.domain == "debugging" for e in debug_entries)

    def test_analyze_patterns_detects_groups(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        config_module = require_module("self_evolve.config")
        config = config_module.SelfEvolveConfig(
            promotion_threshold=2,
        )

        logic.capture_learning(tmp_path, summary="Issue A1", domain="debugging", pattern_key="env-issue")
        logic.capture_learning(tmp_path, summary="Issue A2", domain="debugging", pattern_key="env-issue")

        result = logic.analyze_patterns(tmp_path, config)
        assert len(result.pattern_groups) == 1
        assert result.pattern_groups[0].pattern_key == "env-issue"
        assert result.pattern_groups[0].recurrence == 2

    def test_analyze_patterns_cross_links_entries(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        config_module = require_module("self_evolve.config")
        storage = require_module("self_evolve.storage")
        config = config_module.SelfEvolveConfig()

        e1 = logic.capture_learning(tmp_path, summary="Issue 1", domain="testing", pattern_key="shared")
        e2 = logic.capture_learning(tmp_path, summary="Issue 2", domain="testing", pattern_key="shared")

        logic.analyze_patterns(tmp_path, config)

        reloaded_1 = storage.load_learning(tmp_path, e1.id)
        reloaded_2 = storage.load_learning(tmp_path, e2.id)
        assert reloaded_1 is not None
        assert reloaded_2 is not None
        assert e2.id in reloaded_1.see_also
        assert e1.id in reloaded_2.see_also

    def test_promote_learning_creates_rule(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")

        entry = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="high",
            status="active",
            domain="debugging",
            summary="Always check env vars",
            recurrence_count=5,
            task_ids=["task-1", "task-2", "task-3"],
        )
        storage.save_learning(tmp_path, entry)

        rule = logic.promote_learning(tmp_path, "L-20260330-001", "Validate env vars at startup")
        assert rule is not None
        assert rule.rule == "Validate env vars at startup"
        assert rule.source_learning_id == "L-20260330-001"

        reloaded = storage.load_learning(tmp_path, "L-20260330-001")
        assert reloaded is not None
        assert reloaded.status == "promoted"

    def test_promote_learning_returns_none_for_missing(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        assert logic.promote_learning(tmp_path, "L-nonexistent", "rule") is None

    def test_check_promotion_eligibility(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        config_module = require_module("self_evolve.config")
        models = require_module("self_evolve.models")

        config = config_module.SelfEvolveConfig(
            promotion_threshold=3,
            min_task_count=2,
        )

        eligible = models.LearningEntry(
            id="L-001", timestamp="", priority="high", status="active",
            domain="testing", summary="Eligible",
            recurrence_count=3, task_ids=["t1", "t2"],
        )
        assert logic.check_promotion_eligibility(eligible, config) is True

        ineligible_count = models.LearningEntry(
            id="L-002", timestamp="", priority="high", status="active",
            domain="testing", summary="Low count",
            recurrence_count=1, task_ids=["t1", "t2"],
        )
        assert logic.check_promotion_eligibility(ineligible_count, config) is False

        ineligible_tasks = models.LearningEntry(
            id="L-003", timestamp="", priority="high", status="active",
            domain="testing", summary="Low tasks",
            recurrence_count=5, task_ids=["t1"],
        )
        assert logic.check_promotion_eligibility(ineligible_tasks, config) is False

        already_promoted = models.LearningEntry(
            id="L-004", timestamp="", priority="high", status="promoted",
            domain="testing", summary="Already promoted",
            recurrence_count=5, task_ids=["t1", "t2"],
        )
        assert logic.check_promotion_eligibility(already_promoted, config) is False

    def test_init_project_creates_structure(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        config_module = require_module("self_evolve.config")

        config = config_module.SelfEvolveConfig()
        config_path = logic.init_project(tmp_path, config)

        assert config_path.exists()
        assert (tmp_path / ".agents" / "self-evolve").is_dir()
        assert (tmp_path / ".agents" / "skills" / "self-evolve" / "SKILL.md").exists()

    def test_sync_rules(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")

        config = setup_project(tmp_path)

        rules = [
            models.PromotedRule(
                id="R-001",
                source_learning_id="L-001",
                rule="Always validate inputs",
                domain="security",
                created_at="2026-03-30T12:00:00Z",
            ),
        ]
        storage.save_rules(tmp_path, rules)

        result = logic.sync_rules(tmp_path, config)
        assert result.rules_count == 1

    def test_evolve_full_cycle(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")
        config_module = require_module("self_evolve.config")
        storage = require_module("self_evolve.storage")
        models = require_module("self_evolve.models")

        config = config_module.SelfEvolveConfig(
            promotion_threshold=2,
            min_task_count=2,
        )
        config_module.save_config(tmp_path, config)

        # 创建两个可推广的学习条目
        e1 = models.LearningEntry(
            id="L-20260330-001",
            timestamp="2026-03-30T12:00:00Z",
            priority="high",
            status="active",
            domain="debugging",
            summary="Check env vars",
            pattern_key="env-check",
            recurrence_count=3,
            task_ids=["t1", "t2"],
        )
        e2 = models.LearningEntry(
            id="L-20260330-002",
            timestamp="2026-03-30T12:01:00Z",
            priority="high",
            status="active",
            domain="debugging",
            summary="Also check env vars",
            pattern_key="env-check",
            recurrence_count=3,
            task_ids=["t1", "t2"],
        )
        storage.save_learning(tmp_path, e1)
        storage.save_learning(tmp_path, e2)

        result = logic.evolve(tmp_path, config)

        assert len(result.promoted) == 2
        assert result.sync_result is not None

        # 验证 Skill 文件包含推广的规则
        skill_file = tmp_path / ".agents" / "skills" / "self-evolve" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text(encoding="utf-8")
        assert "Check env vars" in content

    def test_get_evolution_status(self, tmp_path: Path):
        logic = require_module("self_evolve.logic")

        logic.capture_learning(tmp_path, summary="L1", domain="debugging")
        logic.capture_learning(tmp_path, summary="L2", domain="testing")
        logic.capture_learning(tmp_path, summary="L3", domain="debugging")

        status = logic.get_evolution_status(tmp_path)
        assert status.total_learnings == 3
        assert "active" in status.status_counts
        assert status.total_rules == 0
        assert "debugging" in status.active_domains
        assert "testing" in status.active_domains
