"""状态统计。"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from self_evolve.config import rules_dir, skill_dir
from self_evolve.storage import list_rules


@dataclass(slots=True, frozen=True)
class SelfEvolveStatus:
    rule_counts: dict[str, int]
    domain_distribution: dict[str, int]
    strategy: str
    last_synced: str | None
    needs_sync: bool


def get_status(project_root: Path, *, inline_threshold: int = 20) -> SelfEvolveStatus:
    rules = list_rules(project_root)
    active_rules = [r for r in rules if r.status == "active"]

    domain_counts: dict[str, int] = {}
    for r in active_rules:
        domain_counts[r.domain] = domain_counts.get(r.domain, 0) + 1
    domain_distribution = dict(sorted(domain_counts.items()))

    strategy = "inline" if len(active_rules) <= inline_threshold else "index"

    last_synced = _read_last_synced(skill_dir(project_root) / "catalog.json")

    needs_sync = _check_needs_sync(
        rules_dir(project_root),
        skill_dir(project_root) / "SKILL.md",
    )

    return SelfEvolveStatus(
        rule_counts=dict(Counter(rule.status for rule in rules)),
        domain_distribution=domain_distribution,
        strategy=strategy,
        last_synced=last_synced,
        needs_sync=needs_sync,
    )


def _read_last_synced(catalog_path: Path) -> str | None:
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        value = data.get("last_synced")
        return str(value) if value is not None else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _check_needs_sync(rd: Path, skill_md: Path) -> bool:
    if not rd.exists() or not skill_md.exists():
        return True
    rule_files = list(rd.glob("R-*.json"))
    if not rule_files:
        return True
    max_rule_mtime = max(f.stat().st_mtime for f in rule_files)
    skill_mtime = skill_md.stat().st_mtime
    return max_rule_mtime > skill_mtime
