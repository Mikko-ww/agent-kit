from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from self_evolve.config import SelfEvolveConfig
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


def capture_learning(
    data_root: Path,
    *,
    summary: str,
    domain: str,
    priority: str = "medium",
    detail: str = "",
    suggested_action: str = "",
    pattern_key: str = "",
    task_id: str = "",
) -> LearningEntry:
    existing_ids = list_learning_ids(data_root)
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

    save_learning(data_root, entry)
    return entry


def filter_learnings(
    data_root: Path,
    *,
    status: str | None = None,
    domain: str | None = None,
    priority: str | None = None,
    limit: int = 20,
) -> list[LearningEntry]:
    entries = list_learnings(data_root)

    if status:
        entries = [e for e in entries if e.status == status]
    if domain:
        entries = [e for e in entries if e.domain == domain]
    if priority:
        entries = [e for e in entries if e.priority == priority]

    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries[:limit]


def analyze_patterns(data_root: Path, config: SelfEvolveConfig) -> AnalysisResult:
    entries = list_learnings(data_root)

    groups_by_key: dict[str, list[LearningEntry]] = {}
    for entry in entries:
        if entry.pattern_key:
            groups_by_key.setdefault(entry.pattern_key, []).append(entry)

    pattern_groups: list[PatternGroup] = []
    for key, group_entries in sorted(groups_by_key.items()):
        if len(group_entries) < 2:
            continue
        recurrence = len(group_entries)

        _cross_link(group_entries, data_root)

        for entry in group_entries:
            if entry.recurrence_count < recurrence:
                entry.recurrence_count = recurrence
                save_learning(data_root, entry)

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


def check_promotion_eligibility(entry: LearningEntry, config: SelfEvolveConfig) -> bool:
    return _is_promotion_eligible(entry, config)


def promote_learning(
    data_root: Path,
    learning_id: str,
    rule_text: str,
) -> PromotedRule | None:
    entry = load_learning(data_root, learning_id)
    if entry is None:
        return None

    rules = load_rules(data_root)
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
    save_rules(data_root, rules)

    entry.status = "promoted"
    save_learning(data_root, entry)

    return rule


def extract_skill(
    data_root: Path,
    learning_id: str,
    skill_name: str,
    skills_target_dir: Path,
) -> Path | None:
    entry = load_learning(data_root, learning_id)
    if entry is None:
        return None

    skill_dir = skills_target_dir / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_md = skill_dir / "SKILL.md"
    content = _build_skill_content(entry, skill_name)
    skill_md.write_text(content, encoding="utf-8")

    entry.status = "promoted_to_skill"
    save_learning(data_root, entry)

    return skill_dir


def get_evolution_status(data_root: Path) -> EvolutionStatus:
    entries = list_learnings(data_root)
    rules = load_rules(data_root)

    status_counts: dict[str, int] = dict(Counter(e.status for e in entries))
    domains = sorted({e.domain for e in entries if e.status == "active"})

    return EvolutionStatus(
        total_learnings=len(entries),
        status_counts=status_counts,
        total_rules=len(rules),
        total_skills=status_counts.get("promoted_to_skill", 0),
        active_domains=domains,
    )


def _is_promotion_eligible(entry: LearningEntry, config: SelfEvolveConfig) -> bool:
    if entry.status in ("promoted", "promoted_to_skill"):
        return False

    if entry.recurrence_count < config.promotion_threshold:
        return False

    if len(entry.task_ids) < config.min_task_count:
        return False

    return True


def _cross_link(entries: list[LearningEntry], data_root: Path) -> None:
    entry_ids = {e.id for e in entries}
    changed = False
    for entry in entries:
        new_links = entry_ids - {entry.id} - set(entry.see_also)
        if new_links:
            entry.see_also = sorted(set(entry.see_also) | new_links)
            changed = True

    if changed:
        for entry in entries:
            save_learning(data_root, entry)


def _build_skill_content(entry: LearningEntry, skill_name: str) -> str:
    lines = [
        "---",
        f"name: {skill_name}",
        f"description: {entry.summary}",
        "---",
        "",
        f"# {skill_name}",
        "",
        f"## Summary",
        "",
        entry.summary,
        "",
    ]

    if entry.detail:
        lines.extend([
            "## Detail",
            "",
            entry.detail,
            "",
        ])

    if entry.suggested_action:
        lines.extend([
            "## Suggested Action",
            "",
            entry.suggested_action,
            "",
        ])

    lines.extend([
        "## Metadata",
        "",
        f"- Domain: {entry.domain}",
        f"- Source: {entry.id}",
        f"- Extracted: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
    ])

    return "\n".join(lines)
