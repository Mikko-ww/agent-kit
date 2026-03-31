from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from self_evolve.storage import list_candidates, list_rules, list_sessions


@dataclass(slots=True, frozen=True)
class SelfEvolveStatus:
    total_sessions: int
    processed_sessions: int
    pending_sessions: int
    candidate_counts: dict[str, int]
    rule_counts: dict[str, int]


def get_status(project_root: Path) -> SelfEvolveStatus:
    sessions = list_sessions(project_root)
    candidates = list_candidates(project_root)
    rules = list_rules(project_root)
    processed = sum(1 for session in sessions if session.processed)
    return SelfEvolveStatus(
        total_sessions=len(sessions),
        processed_sessions=processed,
        pending_sessions=len(sessions) - processed,
        candidate_counts=dict(Counter(candidate.status for candidate in candidates)),
        rule_counts=dict(Counter(rule.status for rule in rules)),
    )
