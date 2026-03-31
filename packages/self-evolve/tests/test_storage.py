from pathlib import Path

from self_evolve.models import KnowledgeRule
from self_evolve.storage import list_rules, load_rule, save_rule


def _make_rule(rule_id: str = "R-001", status: str = "active") -> KnowledgeRule:
    return KnowledgeRule(
        id=rule_id,
        created_at="2026-03-31T12:00:00Z",
        status=status,
        title="Test",
        statement="S",
        rationale="R",
        domain="testing",
        tags=["ci"],
    )


def test_save_and_load_rule(tmp_path: Path):
    rule = _make_rule()
    path = save_rule(tmp_path, rule)
    assert path.exists()
    loaded = load_rule(tmp_path, "R-001")
    assert loaded is not None
    assert loaded.id == "R-001"
    assert loaded.title == "Test"


def test_load_rule_returns_none_when_missing(tmp_path: Path):
    assert load_rule(tmp_path, "R-999") is None


def test_list_rules(tmp_path: Path):
    save_rule(tmp_path, _make_rule("R-001"))
    save_rule(tmp_path, _make_rule("R-002"))
    rules = list_rules(tmp_path)
    assert len(rules) == 2
    assert rules[0].id == "R-001"
    assert rules[1].id == "R-002"


def test_list_rules_empty(tmp_path: Path):
    assert list_rules(tmp_path) == []
