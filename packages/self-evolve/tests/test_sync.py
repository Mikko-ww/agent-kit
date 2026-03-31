from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from self_evolve.models import KnowledgeRule
from self_evolve.storage import save_rule
from self_evolve.sync import sync_skill


def test_sync_only_renders_active_rules(tmp_path: Path):
    save_rule(
        tmp_path,
        KnowledgeRule(
            id="R-001",
            created_at="2026-03-31T00:00:00+00:00",
            status="active",
            title="Validate env before boot",
            statement="Validate required environment variables before booting the service.",
            rationale="Prevents partial startup failure.",
            domain="debugging",
            tags=["env"],
            source_session_ids=["S-001"],
            source_candidate_ids=["C-001"],
            revision_of="",
        ),
    )
    save_rule(
        tmp_path,
        KnowledgeRule(
            id="R-002",
            created_at="2026-03-31T00:00:00+00:00",
            status="retired",
            title="Old rule",
            statement="Old statement",
            rationale="Old rationale",
            domain="debugging",
            tags=[],
            source_session_ids=[],
            source_candidate_ids=[],
            revision_of="",
        ),
    )

    result = sync_skill(tmp_path)

    content = result.path.read_text(encoding="utf-8")
    assert "Validate env before boot" in content
    assert "Old rule" not in content

    catalog = json.loads(result.catalog_path.read_text(encoding="utf-8"))
    assert catalog["version"] == 2
    assert len(catalog["rules"]) == 1
    assert catalog["rules"][0]["source_candidates"] == ["C-001"]


def test_sync_uses_index_strategy_when_rules_exceed_threshold(tmp_path: Path):
    for i in range(1, 23):
        save_rule(
            tmp_path,
            KnowledgeRule(
                id=f"R-{i:03d}",
                created_at="2026-03-31T00:00:00+00:00",
                status="active",
                title=f"Rule {i}",
                statement=f"Statement {i}",
                rationale=f"Rationale {i}",
                domain="debugging" if i % 2 else "testing",
                tags=[],
                source_session_ids=[],
                source_candidate_ids=[],
                revision_of="",
            ),
        )

    result = sync_skill(tmp_path, inline_threshold=20)

    assert result.strategy == "index"
    assert len(result.domain_files) == 2


def test_find_rules_script_reads_catalog_v2(tmp_path: Path):
    save_rule(
        tmp_path,
        KnowledgeRule(
            id="R-001",
            created_at="2026-03-31T00:00:00+00:00",
            status="active",
            title="Validate env before boot",
            statement="Validate required environment variables before booting the service.",
            rationale="Prevents partial startup failure.",
            domain="debugging",
            tags=["env"],
            source_session_ids=["S-001"],
            source_candidate_ids=["C-001"],
            revision_of="",
        ),
    )
    result = sync_skill(tmp_path)

    script = result.script_path
    output = subprocess.run(
        [sys.executable, str(script), "--keyword", "Validate", "--detail"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "R-001" in output.stdout
    assert "C-001" in output.stdout
