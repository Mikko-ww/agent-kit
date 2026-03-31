#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_catalog(script_dir: Path) -> dict | None:
    path = script_dir.parent / "catalog.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def filter_rules(catalog: dict, *, domain: str | None = None, tag: str | None = None, keyword: str | None = None) -> list[dict]:
    rules = catalog.get("rules", [])
    results = []
    for rule in rules:
        if domain and rule.get("domain") != domain:
            continue
        if tag and tag not in rule.get("tags", []):
            continue
        if keyword:
            needle = keyword.lower()
            haystack = " ".join(
                [
                    str(rule.get("title", "")),
                    str(rule.get("statement", "")),
                    str(rule.get("rationale", "")),
                ]
            ).lower()
            if needle not in haystack:
                continue
        results.append(rule)
    return results


def print_stats(catalog: dict) -> None:
    summary = catalog.get("summary", {})
    print(f"Total rules: {summary.get('total_rules', 0)}")
    for domain, count in sorted(summary.get("domains", {}).items()):
        print(f"{domain}: {count}")


def print_rules(rules: list[dict], *, detail: bool = False) -> None:
    if not rules:
        print("No matching rules.")
        return
    for rule in rules:
        print(f"[{rule.get('domain')}] {rule.get('id')}: {rule.get('title')}")
        if detail:
            print(f"  Statement: {rule.get('statement', '')}")
            print(f"  Rationale: {rule.get('rationale', '')}")
            print(f"  Source sessions: {', '.join(rule.get('source_sessions', [])) or 'none'}")
            print(f"  Source candidates: {', '.join(rule.get('source_candidates', [])) or 'none'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search generated self-evolve rules.")
    parser.add_argument("--domain")
    parser.add_argument("--tag")
    parser.add_argument("--keyword")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()

    catalog = load_catalog(Path(__file__).resolve().parent)
    if catalog is None:
        print("catalog.json not found. Run 'agent-kit self-evolve sync' first.", file=sys.stderr)
        sys.exit(1)

    if args.stats or (not args.domain and not args.tag and not args.keyword):
        print_stats(catalog)
        return

    print_rules(
        filter_rules(catalog, domain=args.domain, tag=args.tag, keyword=args.keyword),
        detail=args.detail,
    )


if __name__ == "__main__":
    main()
