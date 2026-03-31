"""将推广规则同步为统一的 Agent Skill 文件（.agents/skills/self-evolve/SKILL.md）。

支持两种渲染策略：
- 内联模式（规则 ≤ inline_threshold）：规则直接嵌入 SKILL.md
- 索引模式（规则 > inline_threshold）：SKILL.md 仅保留概览，详情拆分到 domains/ 文件
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from self_evolve.config import skill_dir
from self_evolve.models import PromotedRule

# 模板和脚本所在的源码目录
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_SCRIPTS_DIR = Path(__file__).parent / "scripts"


@dataclass(slots=True, frozen=True)
class SyncResult:
    path: Path
    rules_count: int
    strategy: str = "inline"
    domain_files: list[Path] = field(default_factory=list)
    catalog_path: Path | None = None
    script_path: Path | None = None


def sync_skill(
    project_root: Path,
    rules: list[PromotedRule],
    *,
    inline_threshold: int = 20,
) -> SyncResult:
    """将规则同步到 .agents/skills/self-evolve/。"""
    output_dir = skill_dir(project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    strategy = _determine_strategy(rules, inline_threshold)

    # 渲染 SKILL.md
    skill_path = output_dir / "SKILL.md"
    skill_content = _render_skill_md(rules, strategy)
    skill_path.write_text(skill_content, encoding="utf-8")

    # 生成 catalog.json（始终生成，供脚本使用）
    catalog_path = _render_catalog(output_dir, rules)

    # 索引模式下生成域文件
    domain_files: list[Path] = []
    if strategy == "index":
        domain_files = _render_domain_files(output_dir, rules)
        _cleanup_stale_domains(output_dir, rules)

    # 同步检索脚本到项目
    script_path = _sync_scripts(output_dir)

    return SyncResult(
        path=skill_path,
        rules_count=len(rules),
        strategy=strategy,
        domain_files=domain_files,
        catalog_path=catalog_path,
        script_path=script_path,
    )


# ── 策略判断 ──────────────────────────────────────────────────────


def _determine_strategy(rules: list[PromotedRule], threshold: int) -> str:
    """根据规则数量决定渲染策略。"""
    return "inline" if len(rules) <= threshold else "index"


# ── SKILL.md 渲染 ────────────────────────────────────────────────────


def _render_skill_md(rules: list[PromotedRule], strategy: str) -> str:
    """渲染 SKILL.md 主文件。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if strategy == "inline":
        rules_section = _render_inline_section(rules)
    else:
        rules_section = _render_index_section(rules)

    description = _build_description(rules)

    main_tpl = _load_template("skill_main.md.tpl")
    return main_tpl.safe_substitute(
        description=description,
        rules_section=rules_section,
        last_synced=now,
    )


def _build_description(rules: list[PromotedRule]) -> str:
    """构建 SKILL.md 的 description。"""
    if not rules:
        return "当你在项目中工作时使用。本项目尚未积累经验规则，请在工作中通过 capture 命令捕获学习。"

    domains = sorted({r.domain for r in rules})
    domain_str = "、".join(domains)
    return f"当你在项目中工作时使用。包含从项目实践中积累的经验规则，涵盖{domain_str}等领域的实证最佳实践。"


def _render_inline_section(rules: list[PromotedRule]) -> str:
    """内联模式：所有规则按域分组直接嵌入。"""
    if not rules:
        return "> 暂无推广规则。在工作中使用 `capture` 命令积累学习，达到推广条件后通过 `evolve` 生成规则。"

    grouped = _group_by_domain(rules)
    parts: list[str] = []
    for domain in sorted(grouped.keys()):
        parts.append(f"### {domain}\n")
        for rule in grouped[domain]:
            title = rule.title or rule.rule
            tags_str = f" `{', '.join(rule.tags)}`" if rule.tags else ""
            parts.append(f"- **{rule.id}**: {title}{tags_str}")
        parts.append("")

    tpl = _load_template("skill_inline.md.tpl")
    return tpl.safe_substitute(domain_groups="\n".join(parts))


def _render_index_section(rules: list[PromotedRule]) -> str:
    """索引模式：只显示概览表格。"""
    grouped = _group_by_domain(rules)
    rows: list[str] = []
    for domain in sorted(grouped.keys()):
        domain_rules = grouped[domain]
        latest = max(r.created_at[:10] for r in domain_rules) if domain_rules else ""
        rows.append(f"| {domain} | {len(domain_rules)} | {latest} |")

    tpl = _load_template("skill_index.md.tpl")
    return tpl.safe_substitute(domain_table_rows="\n".join(rows))


# ── catalog.json ──────────────────────────────────────────────────


def _render_catalog(output_dir: Path, rules: list[PromotedRule]) -> Path:
    """生成 catalog.json 结构化索引。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    grouped = _group_by_domain(rules)

    catalog = {
        "version": 1,
        "last_synced": now,
        "summary": {
            "total_rules": len(rules),
            "domains": {d: len(rs) for d, rs in sorted(grouped.items())},
        },
        "rules": [_rule_to_catalog_entry(r) for r in rules],
    }

    path = output_dir / "catalog.json"
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _rule_to_catalog_entry(rule: PromotedRule) -> dict[str, object]:
    """将 PromotedRule 转为 catalog 条目。"""
    return {
        "id": rule.id,
        "domain": rule.domain,
        "tags": list(rule.tags),
        "title": rule.title or rule.rule,
        "summary": rule.rule,
        "source_entries": [rule.source_learning_id],
        "promoted_at": rule.created_at[:10] if rule.created_at else "",
    }


# ── 域文件 ────────────────────────────────────────────────────────


def _render_domain_files(output_dir: Path, rules: list[PromotedRule]) -> list[Path]:
    """按域生成详情文件。"""
    domains_dir = output_dir / "domains"
    domains_dir.mkdir(parents=True, exist_ok=True)

    grouped = _group_by_domain(rules)
    tpl = _load_template("domain_detail.md.tpl")
    paths: list[Path] = []

    for domain in sorted(grouped.keys()):
        domain_rules = grouped[domain]
        rules_content = _render_domain_rules(domain_rules)
        content = tpl.safe_substitute(domain=domain, rules_content=rules_content)
        path = domains_dir / f"{domain}.md"
        path.write_text(content, encoding="utf-8")
        paths.append(path)

    return paths


def _render_domain_rules(rules: list[PromotedRule]) -> str:
    """渲染单个域的所有规则。"""
    parts: list[str] = []
    for rule in rules:
        title = rule.title or rule.rule
        parts.append(f"## {rule.id}: {title}")
        tags_str = ", ".join(rule.tags) if rule.tags else "无"
        parts.append(f"- **标签**: {tags_str}")
        parts.append(f"- **来源**: {rule.source_learning_id}")
        parts.append(f"- **推广时间**: {rule.created_at[:10] if rule.created_at else '未知'}")
        parts.append("")
        parts.append(rule.rule)
        parts.append("")
        parts.append("---")
        parts.append("")
    return "\n".join(parts)


def _cleanup_stale_domains(output_dir: Path, rules: list[PromotedRule]) -> None:
    """清理不再使用的域文件。"""
    domains_dir = output_dir / "domains"
    if not domains_dir.exists():
        return

    active_domains = {r.domain for r in rules}
    for path in domains_dir.iterdir():
        if path.suffix == ".md" and path.stem not in active_domains:
            path.unlink()


# ── 脚本同步 ──────────────────────────────────────────────────────


def _sync_scripts(output_dir: Path) -> Path:
    """将 find_rules.py 复制到项目。"""
    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    src = _SCRIPTS_DIR / "find_rules.py"
    dst = scripts_dir / "find_rules.py"
    shutil.copy2(src, dst)
    return dst


# ── 辅助函数 ──────────────────────────────────────────────────────


def _group_by_domain(rules: list[PromotedRule]) -> dict[str, list[PromotedRule]]:
    """按域分组规则。"""
    grouped: dict[str, list[PromotedRule]] = defaultdict(list)
    for rule in rules:
        grouped[rule.domain].append(rule)
    return dict(grouped)


def _load_template(name: str) -> Template:
    """加载模板文件。"""
    path = _TEMPLATES_DIR / name
    return Template(path.read_text(encoding="utf-8"))


def _load_catalog(project_root: Path) -> dict | None:
    """加载项目的 catalog.json，供 search 命令使用。"""
    path = skill_dir(project_root) / "catalog.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
