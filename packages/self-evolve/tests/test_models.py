from __future__ import annotations

from self_evolve.ids import generate_candidate_id, generate_rule_id, generate_session_id
from self_evolve.models import (
    KnowledgeCandidate,
    KnowledgeIndex,
    KnowledgeRule,
    SessionRecord,
)


def test_session_record_round_trip():
    session = SessionRecord(
        id="S-20260331-001",
        created_at="2026-03-31T00:00:00+00:00",
        source="agent",
        summary="Fix flaky startup validation",
        domain="debugging",
        outcome="success",
        observations=["env missing in CI"],
        decisions=["move validation earlier"],
        fixes=["added startup guard"],
        lessons=["validate env before service boot"],
        files=["src/app.py"],
        tags=["env", "startup"],
        processed=False,
    )

    assert SessionRecord.from_dict(session.to_dict()) == session


def test_candidate_round_trip():
    candidate = KnowledgeCandidate(
        id="C-001",
        created_at="2026-03-31T00:00:00+00:00",
        status="open",
        title="Validate env before boot",
        statement="Validate required environment variables before booting the service.",
        rationale="Prevents partial startup failure.",
        domain="debugging",
        tags=["env"],
        confidence=0.85,
        fingerprint="debugging:validate-required-environment-variables-before-booting-the-service",
        source_session_ids=["S-20260331-001"],
        derived_from="lesson",
    )

    assert KnowledgeCandidate.from_dict(candidate.to_dict()) == candidate


def test_rule_round_trip():
    rule = KnowledgeRule(
        id="R-001",
        created_at="2026-03-31T00:00:00+00:00",
        status="active",
        title="Validate env before boot",
        statement="Validate required environment variables before booting the service.",
        rationale="Prevents partial startup failure.",
        domain="debugging",
        tags=["env"],
        source_session_ids=["S-20260331-001"],
        source_candidate_ids=["C-001"],
        revision_of="",
    )

    assert KnowledgeRule.from_dict(rule.to_dict()) == rule


def test_index_round_trip():
    index = KnowledgeIndex(
        fingerprint_to_candidate_ids={"fp": ["C-001"]},
        fingerprint_to_rule_ids={"fp": ["R-001"]},
        session_to_candidate_ids={"S-001": ["C-001"]},
        candidate_to_rule_id={"C-001": "R-001"},
        active_rule_by_fingerprint={"fp": "R-001"},
    )

    assert KnowledgeIndex.from_dict(index.to_dict()) == index


def test_id_generators_increment():
    assert generate_session_id(["S-20260331-001", "S-20260331-002"], now_utc="20260331") == "S-20260331-003"
    assert generate_candidate_id(["C-001", "C-002"]) == "C-003"
    assert generate_rule_id(["R-001", "R-002"]) == "R-003"
