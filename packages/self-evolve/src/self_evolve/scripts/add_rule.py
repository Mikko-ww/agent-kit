#!/usr/bin/env python3
"""Add a new rule to the self-evolve knowledge base. Zero dependencies."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    """从 .agents/skills/self-evolve/scripts/ 推算到 .agents/self-evolve/rules/"""
    agents_dir = script_dir.parent.parent.parent  # scripts/ → self-evolve/ → skills/ → .agents/
    return agents_dir / "self-evolve" / "rules"


def _next_rule_id(rules_dir: Path) -> str:
    max_seq = 0
    if rules_dir.exists():
        for path in rules_dir.glob("R-*.json"):
            try:
                seq = int(path.stem.split("-", 1)[1])
            except (ValueError, IndexError):
                continue
            max_seq = max(max_seq, seq)
    return f"R-{max_seq + 1:03d}"


def _build_fingerprint(domain: str, statement: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", statement.lower()).strip("-")
    return f"{domain}:{normalized}"


def _check_duplicate(rules_dir: Path, fingerprint: str) -> str | None:
    if not rules_dir.exists():
        return None
    for path in rules_dir.glob("R-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        existing_fp = _build_fingerprint(
            str(data.get("domain", "")), str(data.get("statement", ""))
        )
        if existing_fp == fingerprint and data.get("status") == "active":
            return str(data.get("id", path.stem))
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a new rule to self-evolve.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--statement", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--tag", action="append", default=[])
    args = parser.parse_args()

    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    rules_dir.mkdir(parents=True, exist_ok=True)

    fingerprint = _build_fingerprint(args.domain, args.statement)
    existing = _check_duplicate(rules_dir, fingerprint)
    if existing:
        print(f"Warning: similar active rule exists: {existing}", file=sys.stderr)

    rule_id = _next_rule_id(rules_dir)
    rule = {
        "id": rule_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "title": args.title,
        "statement": args.statement,
        "rationale": args.rationale,
        "domain": args.domain,
        "tags": sorted(set(args.tag)),
        "revision_of": "",
    }

    path = rules_dir / f"{rule_id}.json"
    path.write_text(json.dumps(rule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created rule: {rule_id} -> {path}")


if __name__ == "__main__":
    main()
