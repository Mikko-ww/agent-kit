from __future__ import annotations

from self_evolve.fingerprints import build_fingerprint
from self_evolve.models import KnowledgeIndex
from self_evolve.storage import load_index, list_candidates, list_rules, save_index


def load_knowledge_index(project_root) -> KnowledgeIndex:
    return load_index(project_root, "knowledge")


def save_knowledge_index(project_root, index: KnowledgeIndex) -> None:
    save_index(project_root, "knowledge", index)


def append_unique(mapping: dict[str, list[str]], key: str, value: str) -> None:
    current = mapping.setdefault(key, [])
    if value not in current:
        current.append(value)


def rebuild_knowledge_index(project_root) -> KnowledgeIndex:
    index = KnowledgeIndex()

    for candidate in list_candidates(project_root):
        append_unique(index.fingerprint_to_candidate_ids, candidate.fingerprint, candidate.id)
        for session_id in candidate.source_session_ids:
            append_unique(index.session_to_candidate_ids, session_id, candidate.id)

    for rule in list_rules(project_root):
        fingerprint = build_fingerprint(rule.domain, rule.statement)
        append_unique(index.fingerprint_to_rule_ids, fingerprint, rule.id)
        for candidate_id in rule.source_candidate_ids:
            index.candidate_to_rule_id[candidate_id] = rule.id
        if rule.status == "active":
            index.active_rule_by_fingerprint[fingerprint] = rule.id

    save_knowledge_index(project_root, index)
    return index
