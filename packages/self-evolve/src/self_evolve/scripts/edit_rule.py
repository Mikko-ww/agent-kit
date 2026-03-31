#!/usr/bin/env python3
"""Edit an existing rule. Zero dependencies."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    agents_dir = script_dir.parent.parent.parent
    return agents_dir / "self-evolve" / "rules"


def main() -> None:
    parser = argparse.ArgumentParser(description="Edit an existing self-evolve rule.")
    parser.add_argument("rule_id")
    parser.add_argument("--title")
    parser.add_argument("--statement")
    parser.add_argument("--rationale")
    parser.add_argument("--domain")
    parser.add_argument("--tag", action="append")
    args = parser.parse_args()

    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    path = rules_dir / f"{args.rule_id}.json"
    if not path.exists():
        print(f"Rule not found: {args.rule_id}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load rule JSON for {args.rule_id}: {exc}", file=sys.stderr)
        sys.exit(1)
    if args.title is not None:
        data["title"] = args.title
    if args.statement is not None:
        data["statement"] = args.statement
    if args.rationale is not None:
        data["rationale"] = args.rationale
    if args.domain is not None:
        data["domain"] = args.domain
    if args.tag is not None:
        data["tags"] = sorted(set(args.tag))

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated rule: {args.rule_id}")


if __name__ == "__main__":
    main()
