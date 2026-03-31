#!/usr/bin/env python3
"""项目自包含的规则检索脚本。

纯 Python stdlib 实现，零外部依赖。
sync 时自动复制到 .agents/skills/self-evolve/scripts/ 目录。

用法:
    python find_rules.py --domain debugging
    python find_rules.py --keyword "超时"
    python find_rules.py --tag performance --detail
    python find_rules.py --stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_catalog(script_dir: Path) -> dict | None:
    """加载 catalog.json。"""
    catalog_path = script_dir.parent / "catalog.json"
    if not catalog_path.exists():
        return None
    with open(catalog_path, encoding="utf-8") as f:
        return json.load(f)


def search_rules(
    catalog: dict,
    *,
    domain: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    """按条件过滤规则。"""
    rules = catalog.get("rules", [])
    results = []
    for rule in rules:
        if domain and rule.get("domain", "") != domain:
            continue
        if tag and tag not in rule.get("tags", []):
            continue
        if keyword:
            kw = keyword.lower()
            title = rule.get("title", "").lower()
            summary = rule.get("summary", "").lower()
            rule_text = rule.get("rule", "").lower()
            if kw not in title and kw not in summary and kw not in rule_text:
                continue
        results.append(rule)
    return results


def print_stats(catalog: dict) -> None:
    """输出域统计概览。"""
    summary = catalog.get("summary", {})
    domains = summary.get("domains", {})
    total = summary.get("total_rules", 0)
    print(f"规则总数: {total}")
    print("按领域统计:")
    for d, count in sorted(domains.items()):
        print(f"  {d}: {count}")


def print_rules(rules: list[dict], *, detail: bool = False) -> None:
    """输出规则列表。"""
    if not rules:
        print("未找到匹配的规则。")
        return
    print(f"找到 {len(rules)} 条规则:\n")
    for rule in rules:
        rid = rule.get("id", "")
        domain = rule.get("domain", "")
        title = rule.get("title", rule.get("summary", ""))
        tags = ", ".join(rule.get("tags", []))
        tag_str = f" (tags: {tags})" if tags else ""
        print(f"[{domain}] {rid}: {title}{tag_str}")
        if detail:
            summary = rule.get("summary", "")
            rule_text = rule.get("rule", "")
            sources = rule.get("source_entries", [])
            promoted_at = rule.get("promoted_at", "")
            if summary:
                print(f"  摘要: {summary}")
            if rule_text and rule_text != summary:
                print(f"  规则: {rule_text}")
            if sources:
                print(f"  来源: {', '.join(sources)}")
            if promoted_at:
                print(f"  推广时间: {promoted_at}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="项目规则检索工具（self-evolve 自动生成）",
    )
    parser.add_argument("--domain", help="按领域过滤")
    parser.add_argument("--tag", help="按标签过滤")
    parser.add_argument("--keyword", help="模糊搜索标题和摘要")
    parser.add_argument("--stats", action="store_true", help="显示域统计概览")
    parser.add_argument("--detail", action="store_true", help="显示详细内容")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    catalog = load_catalog(script_dir)

    if catalog is None:
        print("未找到 catalog.json。请先运行 'agent-kit self-evolve sync'。", file=sys.stderr)
        sys.exit(1)

    if args.stats:
        print_stats(catalog)
        return

    if not args.domain and not args.tag and not args.keyword:
        print_stats(catalog)
        return

    results = search_rules(
        catalog,
        domain=args.domain,
        tag=args.tag,
        keyword=args.keyword,
    )
    print_rules(results, detail=args.detail)


if __name__ == "__main__":
    main()
