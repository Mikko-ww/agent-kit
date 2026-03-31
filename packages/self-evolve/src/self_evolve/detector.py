from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from self_evolve.candidate_ops import accept_candidate
from self_evolve.config import SelfEvolveConfig
from self_evolve.fingerprints import build_fingerprint
from self_evolve.ids import generate_candidate_id
from self_evolve.index_ops import append_unique, load_knowledge_index, save_knowledge_index
from self_evolve.models import KnowledgeCandidate, KnowledgeRule, SessionRecord
from self_evolve.storage import list_candidates, list_rules, list_sessions, save_candidate, save_session


@dataclass(slots=True, frozen=True)
class DetectionRunResult:
    processed_session_ids: list[str]
    candidates: list[KnowledgeCandidate] = field(default_factory=list)
    auto_accepted_rules: list[KnowledgeRule] = field(default_factory=list)


def run_detection(
    project_root: Path,
    config: SelfEvolveConfig,
    *,
    session_ids: list[str] | None = None,
) -> DetectionRunResult:
    sessions = list_sessions(project_root)
    targets = _select_sessions(sessions, session_ids)
    if not targets:
        return DetectionRunResult(processed_session_ids=[])

    index = load_knowledge_index(project_root)
    candidates = list_candidates(project_root)
    rules = list_rules(project_root)
    by_id = {candidate.id: candidate for candidate in candidates}
    open_by_fingerprint = {
        candidate.fingerprint: candidate
        for candidate in candidates
        if candidate.status == "open"
    }

    touched_candidates: list[KnowledgeCandidate] = []
    auto_accepted_rules: list[KnowledgeRule] = []

    for session in targets:
        for derived in _derive_candidates(session):
            fingerprint = build_fingerprint(session.domain, derived.statement)
            existing_open = open_by_fingerprint.get(fingerprint)
            repeated = _has_other_session_evidence(fingerprint, session.id, candidates, rules)
            score = _score_candidate(
                derived_from=derived.derived_from,
                outcome=session.outcome,
                repeated=repeated,
                has_open_candidate=existing_open is not None,
            )

            if existing_open is not None:
                existing_open.source_session_ids = sorted(
                    set(existing_open.source_session_ids) | {session.id}
                )
                existing_open.tags = sorted(set(existing_open.tags) | set(session.tags))
                existing_open.confidence = max(existing_open.confidence, score)
                save_candidate(project_root, existing_open)
                candidate = existing_open
            else:
                candidate = KnowledgeCandidate(
                    id=generate_candidate_id(list(by_id.keys())),
                    created_at=session.created_at,
                    status="open",
                    title=derived.title,
                    statement=derived.statement,
                    rationale=derived.rationale,
                    domain=session.domain,
                    tags=sorted(set(session.tags)),
                    confidence=score,
                    fingerprint=fingerprint,
                    source_session_ids=[session.id],
                    derived_from=derived.derived_from,
                )
                save_candidate(project_root, candidate)
                by_id[candidate.id] = candidate
                open_by_fingerprint[fingerprint] = candidate

            append_unique(index.fingerprint_to_candidate_ids, fingerprint, candidate.id)
            append_unique(index.session_to_candidate_ids, session.id, candidate.id)

            if candidate not in touched_candidates:
                touched_candidates.append(candidate)

            if (
                candidate.status == "open"
                and config.auto_accept_enabled
                and candidate.confidence >= config.auto_accept_min_confidence
                and fingerprint not in index.active_rule_by_fingerprint
            ):
                rule = accept_candidate(project_root, candidate.id, auto=True)
                if rule is not None:
                    index = load_knowledge_index(project_root)
                    candidate = by_id[candidate.id] = _refresh_candidate(project_root, candidate.id)
                    if candidate is not None and candidate not in touched_candidates:
                        touched_candidates.append(candidate)
                    auto_accepted_rules.append(rule)

        session.processed = True
        save_session(project_root, session)

    save_knowledge_index(project_root, index)
    refreshed = [candidate for candidate in (_refresh_candidate(project_root, item.id) for item in touched_candidates) if candidate is not None]
    return DetectionRunResult(
        processed_session_ids=[session.id for session in targets],
        candidates=refreshed,
        auto_accepted_rules=auto_accepted_rules,
    )


@dataclass(slots=True, frozen=True)
class _DerivedCandidate:
    title: str
    statement: str
    rationale: str
    derived_from: str


def _derive_candidates(session: SessionRecord) -> list[_DerivedCandidate]:
    if session.lessons:
        return [
            _DerivedCandidate(
                title=lesson.strip(),
                statement=lesson.strip(),
                rationale=f"Captured from session lesson: {session.summary}",
                derived_from="lesson",
            )
            for lesson in session.lessons
            if lesson.strip()
        ]

    pairs = zip(session.observations, session.fixes)
    derived: list[_DerivedCandidate] = []
    for observation, fix in pairs:
        observation = observation.strip()
        fix = fix.strip()
        if not observation or not fix:
            continue
        statement = f"{observation}. {fix}"
        derived.append(
            _DerivedCandidate(
                title=fix,
                statement=statement,
                rationale=f"Derived from observation and fix in session: {session.summary}",
                derived_from="observation_fix",
            )
        )
    return derived


def _score_candidate(
    *,
    derived_from: str,
    outcome: str,
    repeated: bool,
    has_open_candidate: bool,
) -> float:
    score = 0.70 if derived_from == "lesson" else 0.45
    if outcome == "success":
        score += 0.10
    if repeated:
        score += 0.15
    if has_open_candidate:
        score += 0.05
    return round(min(score, 1.0), 2)


def _has_other_session_evidence(
    fingerprint: str,
    session_id: str,
    candidates: list[KnowledgeCandidate],
    rules: list[KnowledgeRule],
) -> bool:
    session_ids: set[str] = set()
    for candidate in candidates:
        if candidate.fingerprint == fingerprint:
            session_ids.update(candidate.source_session_ids)
    for rule in rules:
        if build_fingerprint(rule.domain, rule.statement) == fingerprint:
            session_ids.update(rule.source_session_ids)
    return any(existing != session_id for existing in session_ids)


def _select_sessions(sessions: list[SessionRecord], session_ids: list[str] | None) -> list[SessionRecord]:
    if session_ids:
        requested = set(session_ids)
        return [session for session in sessions if session.id in requested]
    return [session for session in sessions if not session.processed]


def _refresh_candidate(project_root: Path, candidate_id: str) -> KnowledgeCandidate | None:
    for candidate in list_candidates(project_root):
        if candidate.id == candidate_id:
            return candidate
    return None
