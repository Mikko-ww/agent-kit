#!/usr/bin/env python3
"""Retire a rule. Zero dependencies."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    agents_dir = script_dir.parent.parent.parent
    return agents_dir / "self-evolve" / "rules"


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: retire_rule.py <rule-id>", file=sys.stderr)
        sys.exit(1)

    rule_id = sys.argv[1]
    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    path = rules_dir / f"{rule_id}.json"
    if not path.exists():
        print(f"Rule not found: {rule_id}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "retired"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Retired rule: {rule_id}")


if __name__ == "__main__":
    main()
