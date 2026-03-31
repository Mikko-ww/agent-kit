from self_evolve.models import KnowledgeRule


def test_rule_round_trip():
    rule = KnowledgeRule(
        id="R-001",
        created_at="2026-03-31T12:00:00Z",
        status="active",
        title="Test rule",
        statement="Always test before commit.",
        rationale="Prevents regressions.",
        domain="testing",
        tags=["ci", "quality"],
        revision_of="",
    )
    data = rule.to_dict()
    restored = KnowledgeRule.from_dict(data)
    assert restored.id == rule.id
    assert restored.title == rule.title
    assert restored.tags == rule.tags
    assert restored.revision_of == ""


def test_rule_from_dict_minimal():
    data = {
        "id": "R-002",
        "created_at": "2026-03-31T12:00:00Z",
        "status": "active",
        "title": "Minimal",
        "statement": "S",
        "rationale": "R",
        "domain": "d",
    }
    rule = KnowledgeRule.from_dict(data)
    assert rule.tags == []
    assert rule.revision_of == ""
