from __future__ import annotations

from pathlib import Path

from self_evolve.models import KnowledgeCandidate, KnowledgeIndex, KnowledgeRule, SessionRecord
from self_evolve.storage import (
    load_candidate,
    load_index,
    load_rule,
    load_session,
    save_candidate,
    save_index,
    save_rule,
    save_session,
    list_candidates,
    list_rules,
    list_sessions,
)


def test_save_and_load_session(tmp_path: Path):
    session = SessionRecord(
        id="S-20260331-001",
        created_at="2026-03-31T00:00:00+00:00",
        source="agent",
        summary="Session summary",
        domain="debugging",
        outcome="success",
        observations=["obs"],
        decisions=[],
        fixes=[],
        lessons=["lesson"],
        files=[],
        tags=[],
        processed=False,
    )

    save_session(tmp_path, session)

    assert load_session(tmp_path, session.id) == session
    assert list_sessions(tmp_path) == [session]


def test_save_and_load_candidate(tmp_path: Path):
    candidate = KnowledgeCandidate(
        id="C-001",
        created_at="2026-03-31T00:00:00+00:00",
        status="open",
        title="Title",
        statement="Statement",
        rationale="Rationale",
        domain="debugging",
        tags=["env"],
        confidence=0.8,
        fingerprint="fp",
        source_session_ids=["S-001"],
        derived_from="lesson",
    )

    save_candidate(tmp_path, candidate)

    assert load_candidate(tmp_path, candidate.id) == candidate
    assert list_candidates(tmp_path) == [candidate]


def test_save_and_load_rule(tmp_path: Path):
    rule = KnowledgeRule(
        id="R-001",
        created_at="2026-03-31T00:00:00+00:00",
        status="active",
        title="Title",
        statement="Statement",
        rationale="Rationale",
        domain="debugging",
        tags=["env"],
        source_session_ids=["S-001"],
        source_candidate_ids=["C-001"],
        revision_of="",
    )

    save_rule(tmp_path, rule)

    assert load_rule(tmp_path, rule.id) == rule
    assert list_rules(tmp_path) == [rule]


def test_save_and_load_index(tmp_path: Path):
    index = KnowledgeIndex(
        fingerprint_to_candidate_ids={"fp": ["C-001"]},
        fingerprint_to_rule_ids={"fp": ["R-001"]},
        session_to_candidate_ids={"S-001": ["C-001"]},
        candidate_to_rule_id={"C-001": "R-001"},
        active_rule_by_fingerprint={"fp": "R-001"},
    )

    save_index(tmp_path, "knowledge", index)

    assert load_index(tmp_path, "knowledge") == index
