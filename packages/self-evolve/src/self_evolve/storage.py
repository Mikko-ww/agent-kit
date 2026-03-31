from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, TypeVar

from self_evolve.config import candidates_dir, indexes_dir, rules_dir, sessions_dir
from self_evolve.models import KnowledgeCandidate, KnowledgeIndex, KnowledgeRule, SessionRecord

T = TypeVar("T")


def save_session(project_root: Path, session: SessionRecord) -> Path:
    return _save_entity(sessions_dir(project_root) / f"{session.id}.json", session.to_dict())


def load_session(project_root: Path, session_id: str) -> SessionRecord | None:
    return _load_entity(
        sessions_dir(project_root) / f"{session_id}.json",
        SessionRecord.from_dict,
    )


def list_sessions(project_root: Path) -> list[SessionRecord]:
    return _list_entities(sessions_dir(project_root), SessionRecord.from_dict)


def save_candidate(project_root: Path, candidate: KnowledgeCandidate) -> Path:
    return _save_entity(candidates_dir(project_root) / f"{candidate.id}.json", candidate.to_dict())


def load_candidate(project_root: Path, candidate_id: str) -> KnowledgeCandidate | None:
    return _load_entity(
        candidates_dir(project_root) / f"{candidate_id}.json",
        KnowledgeCandidate.from_dict,
    )


def list_candidates(project_root: Path) -> list[KnowledgeCandidate]:
    return _list_entities(candidates_dir(project_root), KnowledgeCandidate.from_dict)


def save_rule(project_root: Path, rule: KnowledgeRule) -> Path:
    return _save_entity(rules_dir(project_root) / f"{rule.id}.json", rule.to_dict())


def load_rule(project_root: Path, rule_id: str) -> KnowledgeRule | None:
    return _load_entity(
        rules_dir(project_root) / f"{rule_id}.json",
        KnowledgeRule.from_dict,
    )


def list_rules(project_root: Path) -> list[KnowledgeRule]:
    return _list_entities(rules_dir(project_root), KnowledgeRule.from_dict)


def save_index(project_root: Path, name: str, index: KnowledgeIndex) -> Path:
    return _save_entity(indexes_dir(project_root) / f"{name}.json", index.to_dict())


def load_index(project_root: Path, name: str) -> KnowledgeIndex:
    loaded = _load_entity(
        indexes_dir(project_root) / f"{name}.json",
        KnowledgeIndex.from_dict,
    )
    return loaded or KnowledgeIndex()


def _save_entity(path: Path, data: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _load_entity(path: Path, loader: Callable[[dict[str, object]], T]) -> T | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return loader(data)


def _list_entities(directory: Path, loader: Callable[[dict[str, object]], T]) -> list[T]:
    if not directory.exists():
        return []
    entities: list[T] = []
    for path in sorted(directory.glob("*.json")):
        loaded = _load_entity(path, loader)
        if loaded is not None:
            entities.append(loaded)
    return entities
