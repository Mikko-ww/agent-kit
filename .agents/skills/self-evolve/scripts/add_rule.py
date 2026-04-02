#!/usr/bin/env python3
"""Add a new rule to the self-evolve knowledge base. Zero dependencies."""
from __future__ import annotations

import argparse
import hashlib
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
    """构建规则指纹用于重复检测。

    对于包含 Unicode 字符（如中文）的 statement，使用 re.UNICODE 标志确保正确处理。
    如果标准化后为空（仅特殊字符的情况），则使用 MD5 哈希作为后备。
    """
    normalized = re.sub(r"[^\w]+", "-", statement.lower(), flags=re.UNICODE).strip("-")
    if not normalized:
        normalized = hashlib.md5(statement.encode("utf-8")).hexdigest()[:16]
    return f"{domain}:{normalized}"


def _check_duplicate(rules_dir: Path, fingerprint: str) -> str | None:
    """检查是否存在相同指纹的活动规则。

    返回第一个匹配的活动规则 ID，如果没有重复则返回 None。
    忽略损坏的 JSON 文件和非活动状态的规则。
    """
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

    # 验证必填字段不为空
    if not args.title.strip():
        print("Error: title cannot be empty", file=sys.stderr)
        sys.exit(1)
    if not args.statement.strip():
        print("Error: statement cannot be empty", file=sys.stderr)
        sys.exit(1)
    if not args.rationale.strip():
        print("Error: rationale cannot be empty", file=sys.stderr)
        sys.exit(1)
    if not args.domain.strip():
        print("Error: domain cannot be empty", file=sys.stderr)
        sys.exit(1)

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
    try:
        path.write_text(json.dumps(rule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"Failed to write rule file {path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Created rule: {rule_id} -> {path}")


if __name__ == "__main__":
    main()
