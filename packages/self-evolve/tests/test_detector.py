from __future__ import annotations

from self_evolve.candidate_ops import accept_candidate, reject_candidate
from self_evolve.config import SelfEvolveConfig
from self_evolve.detector import run_detection
from self_evolve.rule_ops import add_rule, retire_rule
from self_evolve.session_ops import record_session
from self_evolve.storage import load_candidate, load_index, load_rule, load_session, list_candidates, list_rules


def test_detect_candidate_from_explicit_lesson(tmp_path):
    session = record_session(
        tmp_path,
        summary="Fix startup validation",
        domain="debugging",
        outcome="success",
        lessons=["Validate env before boot"],
        files=["src/app.py"],
        tags=["env"],
    )

    result = run_detection(tmp_path, SelfEvolveConfig())

    assert result.processed_session_ids == [session.id]
    assert len(result.candidates) == 1

    candidate = result.candidates[0]
    assert candidate.title == "Validate env before boot"
    assert candidate.derived_from == "lesson"
    assert candidate.confidence == 0.8
    assert candidate.status == "open"
    assert candidate.source_session_ids == [session.id]

    reloaded = load_session(tmp_path, session.id)
    assert reloaded is not None
    assert reloaded.processed is True


def test_detect_candidate_from_observation_fix_pair_when_no_lessons(tmp_path):
    record_session(
        tmp_path,
        summary="Fix startup validation",
        domain="debugging",
        outcome="partial",
        observations=["Service booted with missing env vars"],
        fixes=["Added startup validation guard"],
    )

    result = run_detection(tmp_path, SelfEvolveConfig())

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.derived_from == "observation_fix"
    assert candidate.confidence == 0.45
    assert "Added startup validation guard" in candidate.statement


def test_detection_merges_same_fingerprint_and_auto_accepts_when_enabled(tmp_path):
    record_session(
        tmp_path,
        summary="First fix",
        domain="debugging",
        outcome="success",
        lessons=["Validate env before boot"],
    )
    run_detection(tmp_path, SelfEvolveConfig())

    second = record_session(
        tmp_path,
        summary="Second fix",
        domain="debugging",
        outcome="success",
        lessons=["Validate env before boot"],
    )

    result = run_detection(
        tmp_path,
        SelfEvolveConfig(auto_accept_enabled=True, auto_accept_min_confidence=0.9),
    )

    assert result.processed_session_ids == [second.id]
    assert len(list_candidates(tmp_path)) == 1
    candidate = list_candidates(tmp_path)[0]
    assert candidate.status == "auto_accepted"
    assert candidate.confidence == 1.0
    assert len(candidate.source_session_ids) == 2

    rules = list_rules(tmp_path)
    assert len(rules) == 1
    index = load_index(tmp_path, "knowledge")
    assert index.active_rule_by_fingerprint[candidate.fingerprint] == rules[0].id


def test_accept_candidate_creates_rule_and_updates_index(tmp_path):
    session = record_session(
        tmp_path,
        summary="Fix startup validation",
        domain="debugging",
        outcome="success",
        lessons=["Validate env before boot"],
    )
    detected = run_detection(tmp_path, SelfEvolveConfig()).candidates[0]

    rule = accept_candidate(tmp_path, detected.id)

    assert rule is not None
    assert rule.source_candidate_ids == [detected.id]
    assert rule.source_session_ids == [session.id]

    candidate = load_candidate(tmp_path, detected.id)
    assert candidate is not None
    assert candidate.status == "accepted"

    index = load_index(tmp_path, "knowledge")
    assert index.candidate_to_rule_id[detected.id] == rule.id


def test_reject_candidate_only_updates_status(tmp_path):
    record_session(
        tmp_path,
        summary="Fix startup validation",
        domain="debugging",
        outcome="success",
        lessons=["Validate env before boot"],
    )
    candidate = run_detection(tmp_path, SelfEvolveConfig()).candidates[0]

    rejected = reject_candidate(tmp_path, candidate.id)

    assert rejected is not None
    assert rejected.status == "rejected"
    assert load_rule(tmp_path, "R-001") is None


def test_add_and_retire_rule_updates_active_index(tmp_path):
    rule = add_rule(
        tmp_path,
        title="Validate env before boot",
        statement="Validate required environment variables before booting the service.",
        rationale="Prevents partial startup failure.",
        domain="debugging",
        tags=["env"],
        source_session_ids=[],
    )

    assert rule.status == "active"

    retired = retire_rule(tmp_path, rule.id)

    assert retired is not None
    assert retired.status == "retired"
    index = load_index(tmp_path, "knowledge")
    assert retired.id not in index.active_rule_by_fingerprint.values()
