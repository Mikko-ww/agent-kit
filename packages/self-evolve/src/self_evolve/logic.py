from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from self_evolve.config import SelfEvolveConfig, evolve_dir, save_config
from self_evolve.models import (
    LearningEntry,
    PromotedRule,
    generate_learning_id,
    generate_rule_id,
)
from self_evolve.storage import (
    list_learning_ids,
    list_learnings,
    load_learning,
    load_rules,
    save_learning,
    save_rules,
)
from self_evolve.sync import SyncResult, sync_to_targets


@dataclass(slots=True, frozen=True)
class PatternGroup:
    pattern_key: str
    entries: list[LearningEntry]
    recurrence: int


@dataclass(slots=True, frozen=True)
class AnalysisResult:
    pattern_groups: list[PatternGroup]
    promotion_candidates: list[LearningEntry]


@dataclass(slots=True, frozen=True)
class EvolutionStatus:
    total_learnings: int
    status_counts: dict[str, int]
    total_rules: int
    total_skills: int
    active_domains: list[str]


@dataclass(slots=True, frozen=True)
class EvolveResult:
    analysis: AnalysisResult
    promoted: list[PromotedRule]
    sync_results: list[SyncResult]


# ── 项目初始化 ─────────────────────────────────────────────────────


def init_project(
    project_root: Path,
    config: SelfEvolveConfig,
) -> Path:
    """在项目根目录创建 .self-evolve/ 并写入配置。"""
    edir = evolve_dir(project_root)
    edir.mkdir(parents=True, exist_ok=True)

    config_path = save_config(project_root, config)

    # 初次同步，生成空的 agent skill 文件
    sync_to_targets(project_root, [], config.targets)

    return config_path


# ── 捕获学习 ──────────────────────────────────────────────────────


def capture_learning(
    project_root: Path,
    *,
    summary: str,
    domain: str,
    priority: str = "medium",
    detail: str = "",
    suggested_action: str = "",
    pattern_key: str = "",
    task_id: str = "",
) -> LearningEntry:
    existing_ids = list_learning_ids(project_root)
    learning_id = generate_learning_id(existing_ids)
    now = datetime.now(timezone.utc).isoformat()

    task_ids = [task_id] if task_id else []

    entry = LearningEntry(
        id=learning_id,
        timestamp=now,
        priority=priority,
        status="active",
        domain=domain,
        summary=summary,
        detail=detail,
        suggested_action=suggested_action,
        pattern_key=pattern_key,
        see_also=[],
        recurrence_count=1,
        task_ids=task_ids,
    )

    save_learning(project_root, entry)
    return entry


# ── 过滤列表 ──────────────────────────────────────────────────────


def filter_learnings(
    project_root: Path,
    *,
    status: str | None = None,
    domain: str | None = None,
    priority: str | None = None,
    limit: int = 20,
) -> list[LearningEntry]:
    entries = list_learnings(project_root)

    if status:
        entries = [e for e in entries if e.status == status]
    if domain:
        entries = [e for e in entries if e.domain == domain]
    if priority:
        entries = [e for e in entries if e.priority == priority]

    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries[:limit]


# ── 模式分析 ──────────────────────────────────────────────────────


def analyze_patterns(project_root: Path, config: SelfEvolveConfig) -> AnalysisResult:
    entries = list_learnings(project_root)

    groups_by_key: dict[str, list[LearningEntry]] = {}
    for entry in entries:
        if entry.pattern_key:
            groups_by_key.setdefault(entry.pattern_key, []).append(entry)

    pattern_groups: list[PatternGroup] = []
    for key, group_entries in sorted(groups_by_key.items()):
        if len(group_entries) < 2:
            continue
        recurrence = len(group_entries)

        _cross_link(group_entries, project_root)

        for entry in group_entries:
            if entry.recurrence_count < recurrence:
                entry.recurrence_count = recurrence
                save_learning(project_root, entry)

        pattern_groups.append(
            PatternGroup(pattern_key=key, entries=group_entries, recurrence=recurrence)
        )

    promotion_candidates: list[LearningEntry] = []
    for group in pattern_groups:
        for entry in group.entries:
            if _is_promotion_eligible(entry, config):
                promotion_candidates.append(entry)

    return AnalysisResult(
        pattern_groups=pattern_groups,
        promotion_candidates=promotion_candidates,
    )


# ── 推广 ──────────────────────────────────────────────────────────


def check_promotion_eligibility(entry: LearningEntry, config: SelfEvolveConfig) -> bool:
    return _is_promotion_eligible(entry, config)


def promote_learning(
    project_root: Path,
    learning_id: str,
    rule_text: str,
) -> PromotedRule | None:
    entry = load_learning(project_root, learning_id)
    if entry is None:
        return None

    rules = load_rules(project_root)
    existing_rule_ids = [r.id for r in rules]
    rule_id = generate_rule_id(existing_rule_ids)
    now = datetime.now(timezone.utc).isoformat()

    rule = PromotedRule(
        id=rule_id,
        source_learning_id=learning_id,
        rule=rule_text,
        domain=entry.domain,
        created_at=now,
    )

    rules.append(rule)
    save_rules(project_root, rules)

    entry.status = "promoted"
    save_learning(project_root, entry)

    return rule


# ── 同步 ──────────────────────────────────────────────────────────


def sync_rules(
    project_root: Path,
    config: SelfEvolveConfig,
) -> list[SyncResult]:
    """将所有推广规则同步到配置的 agent targets。"""
    rules = load_rules(project_root)
    return sync_to_targets(project_root, rules, config.targets)


# ── 一键进化 ──────────────────────────────────────────────────────


def evolve(
    project_root: Path,
    config: SelfEvolveConfig,
) -> EvolveResult:
    """一键完成 analyze → auto-promote → sync 进化循环。"""
    analysis = analyze_patterns(project_root, config)

    promoted: list[PromotedRule] = []
    for entry in analysis.promotion_candidates:
        rule_text = entry.summary
        rule = promote_learning(project_root, entry.id, rule_text)
        if rule:
            promoted.append(rule)

    sync_results = sync_rules(project_root, config)

    return EvolveResult(
        analysis=analysis,
        promoted=promoted,
        sync_results=sync_results,
    )


# ── 状态概览 ──────────────────────────────────────────────────────


def get_evolution_status(project_root: Path) -> EvolutionStatus:
    entries = list_learnings(project_root)
    rules = load_rules(project_root)

    status_counts: dict[str, int] = dict(Counter(e.status for e in entries))
    domains = sorted({e.domain for e in entries if e.status == "active"})

    return EvolutionStatus(
        total_learnings=len(entries),
        status_counts=status_counts,
        total_rules=len(rules),
        total_skills=status_counts.get("promoted_to_skill", 0),
        active_domains=domains,
    )


# ── 内部辅助 ──────────────────────────────────────────────────────


def _is_promotion_eligible(entry: LearningEntry, config: SelfEvolveConfig) -> bool:
    if entry.status in ("promoted", "promoted_to_skill"):
        return False

    if entry.recurrence_count < config.promotion_threshold:
        return False

    if len(entry.task_ids) < config.min_task_count:
        return False

    return True


def _cross_link(entries: list[LearningEntry], project_root: Path) -> None:
    entry_ids = {e.id for e in entries}
    changed = False
    for entry in entries:
        new_links = entry_ids - {entry.id} - set(entry.see_also)
        if new_links:
            entry.see_also = sorted(set(entry.see_also) | new_links)
            changed = True

    if changed:
        for entry in entries:
            save_learning(project_root, entry)
