#!/usr/bin/env python3
"""List rules directly from the rules directory. Zero dependencies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    agents_dir = script_dir.parent.parent.parent
    return agents_dir / "self-evolve" / "rules"


def _load_all_rules(rules_dir: Path) -> list[dict]:
    if not rules_dir.exists():
        return []
    rules = []
    for path in sorted(rules_dir.glob("R-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rules.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return rules


def _filter_rules(
    rules: list[dict],
    *,
    status: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    results = []
    for rule in rules:
        if status and rule.get("status") != status:
            continue
        if domain and rule.get("domain") != domain:
            continue
        if tag and tag not in rule.get("tags", []):
            continue
        if keyword:
            needle = keyword.lower()
            haystack = " ".join([
                str(rule.get("title", "")),
                str(rule.get("statement", "")),
                str(rule.get("rationale", "")),
            ]).lower()
            if needle not in haystack:
                continue
        results.append(rule)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="List self-evolve rules from the rules directory.")
    parser.add_argument("--status")
    parser.add_argument("--domain")
    parser.add_argument("--tag")
    parser.add_argument("--keyword")
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()

    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    all_rules = _load_all_rules(rules_dir)

    if not args.status and not args.domain and not args.tag and not args.keyword:
        args.status = "active"

    filtered = _filter_rules(all_rules, status=args.status, domain=args.domain, tag=args.tag, keyword=args.keyword)
    if not filtered:
        print("No matching rules.")
        return

    for rule in filtered:
        print(f"[{rule.get('status')}] {rule.get('id')}: {rule.get('title')}")
        if args.detail:
            print(f"  Statement: {rule.get('statement', '')}")
            print(f"  Rationale: {rule.get('rationale', '')}")
            print(f"  Domain: {rule.get('domain', '')}")
            print(f"  Tags: {', '.join(rule.get('tags', [])) or 'none'}")


if __name__ == "__main__":
    main()
