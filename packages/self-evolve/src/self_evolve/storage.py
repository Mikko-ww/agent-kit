"""v5 存储层——仅 Rule 持久化。"""

from __future__ import annotations

import json
from pathlib import Path

from self_evolve.config import rules_dir
from self_evolve.models import KnowledgeRule


def save_rule(project_root: Path, rule: KnowledgeRule) -> Path:
    directory = rules_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{rule.id}.json"
    path.write_text(
        json.dumps(rule.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_rule(project_root: Path, rule_id: str) -> KnowledgeRule | None:
    path = rules_dir(project_root) / f"{rule_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return KnowledgeRule.from_dict(data)
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def list_rules(project_root: Path) -> list[KnowledgeRule]:
    directory = rules_dir(project_root)
    if not directory.exists():
        return []
    rules: list[KnowledgeRule] = []
    for path in sorted(directory.glob("R-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rules.append(KnowledgeRule.from_dict(data))
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return rules
