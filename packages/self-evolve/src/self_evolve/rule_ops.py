from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from self_evolve.fingerprints import build_fingerprint
from self_evolve.ids import generate_rule_id
from self_evolve.index_ops import rebuild_knowledge_index
from self_evolve.models import KnowledgeRule
from self_evolve.storage import load_rule, list_rules, save_rule


def add_rule(
    project_root: Path,
    *,
    title: str,
    statement: str,
    rationale: str,
    domain: str,
    tags: list[str] | None = None,
    source_session_ids: list[str] | None = None,
    source_candidate_ids: list[str] | None = None,
) -> KnowledgeRule:
    existing_ids = [rule.id for rule in list_rules(project_root)]
    rule = KnowledgeRule(
        id=generate_rule_id(existing_ids),
        created_at=datetime.now(timezone.utc).isoformat(),
        status="active",
        title=title,
        statement=statement,
        rationale=rationale,
        domain=domain,
        tags=tags or [],
        source_session_ids=source_session_ids or [],
        source_candidate_ids=source_candidate_ids or [],
        revision_of="",
    )
    save_rule(project_root, rule)
    rebuild_knowledge_index(project_root)
    return rule


def retire_rule(project_root: Path, rule_id: str) -> KnowledgeRule | None:
    rule = load_rule(project_root, rule_id)
    if rule is None:
        return None
    rule.status = "retired"
    save_rule(project_root, rule)
    rebuild_knowledge_index(project_root)
    return rule


def edit_rule(
    project_root: Path,
    rule_id: str,
    *,
    title: str | None = None,
    statement: str | None = None,
    rationale: str | None = None,
    domain: str | None = None,
    tags: list[str] | None = None,
    revision_of: str | None = None,
) -> KnowledgeRule | None:
    rule = load_rule(project_root, rule_id)
    if rule is None:
        return None
    if title is not None:
        rule.title = title
    if statement is not None:
        rule.statement = statement
    if rationale is not None:
        rule.rationale = rationale
    if domain is not None:
        rule.domain = domain
    if tags is not None:
        rule.tags = tags
    if revision_of is not None:
        rule.revision_of = revision_of
    save_rule(project_root, rule)
    rebuild_knowledge_index(project_root)
    return rule


def filter_rules(
    project_root: Path,
    *,
    status: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
) -> list[KnowledgeRule]:
    items = list_rules(project_root)
    if status:
        items = [item for item in items if item.status == status]
    if domain:
        items = [item for item in items if item.domain == domain]
    if tag:
        items = [item for item in items if tag in item.tags]
    if keyword:
        needle = keyword.lower()
        items = [
            item
            for item in items
            if needle in item.title.lower()
            or needle in item.statement.lower()
            or needle in item.rationale.lower()
        ]
    items.sort(key=lambda item: item.created_at, reverse=True)
    return items[:limit]
