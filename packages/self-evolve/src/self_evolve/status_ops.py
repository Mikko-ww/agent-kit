"""状态统计。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from self_evolve.storage import list_rules


@dataclass(slots=True, frozen=True)
class SelfEvolveStatus:
    rule_counts: dict[str, int]


def get_status(project_root: Path) -> SelfEvolveStatus:
    rules = list_rules(project_root)
    return SelfEvolveStatus(
        rule_counts=dict(Counter(rule.status for rule in rules)),
    )
