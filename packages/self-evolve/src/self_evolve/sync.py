from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from self_evolve.config import resolve_template_language, skill_dir
from self_evolve.models import KnowledgeRule
from self_evolve.storage import list_rules

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_SCRIPTS_DIR = Path(__file__).parent / "scripts"

_SYNC_COPY = {
    "en": {
        "description.with_rules": "When you work in this project, use these project-approved rules and record new sessions when you learn something reusable.",
        "description.empty": "When you work in this project, no approved rules exist yet. Record sessions and run detection to grow the rule set.",
        "no_active_rules": "> No active rules yet. Record sessions, run detection, review candidates, and sync again.",
        "domain.statement": "Statement",
        "domain.rationale": "Rationale",
        "domain.tags": "Tags",
        "domain.source_sessions": "Source sessions",
        "domain.source_candidates": "Source candidates",
        "none": "none",
    },
    "zh-CN": {
        "description.with_rules": "当你在此项目中工作时，请优先遵循这些已批准的项目规则；若学到可复用经验，请记录新的 session。",
        "description.empty": "当你在此项目中工作时，当前还没有已批准规则。请先记录 session、运行检测，再逐步沉淀规则集。",
        "no_active_rules": "> 当前还没有 active rule。请先记录 session、运行检测、审核 candidate，然后再次同步。",
        "domain.statement": "规则内容",
        "domain.rationale": "原因",
        "domain.tags": "标签",
        "domain.source_sessions": "来源会话",
        "domain.source_candidates": "来源候选",
        "none": "无",
    },
}


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
    *,
    inline_threshold: int = 20,
    language: str | None = None,
) -> SyncResult:
    rules = [rule for rule in list_rules(project_root) if rule.status == "active"]
    output_dir = skill_dir(project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    strategy = "inline" if len(rules) <= inline_threshold else "index"
    resolved_language = language or resolve_template_language(project_root)

    skill_path = output_dir / "SKILL.md"
    skill_path.write_text(_render_skill_md(rules, strategy, resolved_language), encoding="utf-8")
    catalog_path = _render_catalog(output_dir, rules)

    domain_files: list[Path] = []
    if strategy == "index":
        domain_files = _render_domain_files(output_dir, rules, resolved_language)
    _cleanup_stale_domains(output_dir, rules, strategy)

    script_path = _sync_script(output_dir)
    return SyncResult(
        path=skill_path,
        rules_count=len(rules),
        strategy=strategy,
        domain_files=domain_files,
        catalog_path=catalog_path,
        script_path=script_path,
    )


def _render_skill_md(rules: list[KnowledgeRule], strategy: str, language: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    description = (
        _copy(language, "description.with_rules")
        if rules
        else _copy(language, "description.empty")
    )
    section = _render_inline_section(rules, language) if strategy == "inline" else _render_index_section(rules, language)
    return _load_template("skill_main", language).safe_substitute(
        description=description,
        rules_section=section,
        last_synced=now,
    )


def _render_inline_section(rules: list[KnowledgeRule], language: str) -> str:
    if not rules:
        return _copy(language, "no_active_rules")
    grouped = _group_by_domain(rules)
    parts: list[str] = []
    for domain in sorted(grouped):
        parts.append(f"### {domain}\n")
        for rule in grouped[domain]:
            tags = f" (`{', '.join(rule.tags)}`)" if rule.tags else ""
            parts.append(f"- **{rule.id}** {rule.title}: {rule.statement}{tags}")
        parts.append("")
    return _load_template("skill_inline", language).safe_substitute(domain_groups="\n".join(parts))


def _render_index_section(rules: list[KnowledgeRule], language: str) -> str:
    grouped = _group_by_domain(rules)
    rows = [f"| {domain} | {len(items)} | {max(item.created_at[:10] for item in items)} |" for domain, items in sorted(grouped.items())]
    return _load_template("skill_index", language).safe_substitute(domain_table_rows="\n".join(rows))


def _render_catalog(output_dir: Path, rules: list[KnowledgeRule]) -> Path:
    grouped = _group_by_domain(rules)
    payload = {
        "version": 2,
        "last_synced": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "summary": {
            "total_rules": len(rules),
            "domains": {domain: len(items) for domain, items in sorted(grouped.items())},
        },
        "rules": [
            {
                "id": rule.id,
                "title": rule.title,
                "statement": rule.statement,
                "rationale": rule.rationale,
                "domain": rule.domain,
                "tags": list(rule.tags),
                "source_sessions": list(rule.source_session_ids),
                "source_candidates": list(rule.source_candidate_ids),
                "created_at": rule.created_at,
                "revision_of": rule.revision_of,
            }
            for rule in rules
        ],
    }
    path = output_dir / "catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _render_domain_files(output_dir: Path, rules: list[KnowledgeRule], language: str) -> list[Path]:
    grouped = _group_by_domain(rules)
    domains_dir = output_dir / "domains"
    domains_dir.mkdir(parents=True, exist_ok=True)
    template = _load_template("domain_detail", language)
    paths: list[Path] = []
    for domain, items in sorted(grouped.items()):
        body_lines: list[str] = []
        for rule in items:
            body_lines.extend(
                [
                    f"## {rule.id}: {rule.title}",
                    f"- {_copy(language, 'domain.statement')}: {rule.statement}",
                    f"- {_copy(language, 'domain.rationale')}: {rule.rationale}",
                    f"- {_copy(language, 'domain.tags')}: {', '.join(rule.tags) if rule.tags else _copy(language, 'none')}",
                    f"- {_copy(language, 'domain.source_sessions')}: {', '.join(rule.source_session_ids) if rule.source_session_ids else _copy(language, 'none')}",
                    f"- {_copy(language, 'domain.source_candidates')}: {', '.join(rule.source_candidate_ids) if rule.source_candidate_ids else _copy(language, 'none')}",
                    "",
                ]
            )
        path = domains_dir / f"{domain}.md"
        path.write_text(template.safe_substitute(domain=domain, rules_content="\n".join(body_lines)), encoding="utf-8")
        paths.append(path)
    return paths


def _cleanup_stale_domains(output_dir: Path, rules: list[KnowledgeRule], strategy: str) -> None:
    domains_dir = output_dir / "domains"
    if not domains_dir.exists():
        return
    active_domains = {rule.domain for rule in rules} if strategy == "index" else set()
    for path in domains_dir.glob("*.md"):
        if path.stem not in active_domains:
            path.unlink()


def _sync_script(output_dir: Path) -> Path:
    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    source = _SCRIPTS_DIR / "find_rules.py"
    destination = scripts_dir / "find_rules.py"
    shutil.copy2(source, destination)
    return destination


def _group_by_domain(rules: list[KnowledgeRule]) -> dict[str, list[KnowledgeRule]]:
    grouped: dict[str, list[KnowledgeRule]] = defaultdict(list)
    for rule in rules:
        grouped[rule.domain].append(rule)
    return dict(grouped)


def _load_template(name: str, language: str) -> Template:
    normalized_language = language if language in _SYNC_COPY else "en"
    path = _TEMPLATES_DIR / f"{name}.{normalized_language}.md.tpl"
    if not path.exists():
        path = _TEMPLATES_DIR / f"{name}.en.md.tpl"
    return Template(path.read_text(encoding="utf-8"))


def _copy(language: str, key: str) -> str:
    catalog = _SYNC_COPY.get(language, _SYNC_COPY["en"])
    return catalog[key]
