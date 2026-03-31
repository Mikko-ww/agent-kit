from __future__ import annotations

from pathlib import Path

from self_evolve.fingerprints import build_fingerprint
from self_evolve.ids import generate_rule_id
from self_evolve.index_ops import rebuild_knowledge_index
from self_evolve.models import KnowledgeCandidate, KnowledgeRule
from self_evolve.storage import load_candidate, list_candidates, list_rules, save_candidate, save_rule


def accept_candidate(project_root: Path, candidate_id: str, *, auto: bool = False) -> KnowledgeRule | None:
    candidate = load_candidate(project_root, candidate_id)
    if candidate is None:
        return None

    index = rebuild_knowledge_index(project_root)
    if candidate_id in index.candidate_to_rule_id:
        existing_rule_id = index.candidate_to_rule_id[candidate_id]
        existing = next((rule for rule in list_rules(project_root) if rule.id == existing_rule_id), None)
        if existing is not None:
            return existing

    fingerprint = candidate.fingerprint or build_fingerprint(candidate.domain, candidate.statement)
    existing_rule_ids = [rule.id for rule in list_rules(project_root)]
    rule = KnowledgeRule(
        id=generate_rule_id(existing_rule_ids),
        created_at=candidate.created_at,
        status="active",
        title=candidate.title,
        statement=candidate.statement,
        rationale=candidate.rationale,
        domain=candidate.domain,
        tags=list(candidate.tags),
        source_session_ids=list(candidate.source_session_ids),
        source_candidate_ids=[candidate.id],
        revision_of="",
    )
    save_rule(project_root, rule)

    candidate.status = "auto_accepted" if auto else "accepted"
    save_candidate(project_root, candidate)

    for other in list_candidates(project_root):
        if other.id != candidate.id and other.status == "open" and other.fingerprint == fingerprint:
            other.status = "superseded"
            save_candidate(project_root, other)

    rebuild_knowledge_index(project_root)
    return rule


def reject_candidate(project_root: Path, candidate_id: str) -> KnowledgeCandidate | None:
    candidate = load_candidate(project_root, candidate_id)
    if candidate is None:
        return None
    candidate.status = "rejected"
    save_candidate(project_root, candidate)
    rebuild_knowledge_index(project_root)
    return candidate


def edit_candidate(
    project_root: Path,
    candidate_id: str,
    *,
    title: str | None = None,
    statement: str | None = None,
    rationale: str | None = None,
    domain: str | None = None,
    tags: list[str] | None = None,
) -> KnowledgeCandidate | None:
    candidate = load_candidate(project_root, candidate_id)
    if candidate is None:
        return None
    if title is not None:
        candidate.title = title
    if statement is not None:
        candidate.statement = statement
    if rationale is not None:
        candidate.rationale = rationale
    if domain is not None:
        candidate.domain = domain
    if tags is not None:
        candidate.tags = tags
    candidate.fingerprint = build_fingerprint(candidate.domain, candidate.statement)
    save_candidate(project_root, candidate)
    rebuild_knowledge_index(project_root)
    return candidate


def filter_candidates(
    project_root: Path,
    *,
    status: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
) -> list[KnowledgeCandidate]:
    items = list_candidates(project_root)
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
