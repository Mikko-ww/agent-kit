from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from self_evolve.config import skill_dir
from self_evolve.models import KnowledgeRule
from self_evolve.storage import list_rules

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
    *,
    inline_threshold: int = 20,
) -> SyncResult:
    rules = [rule for rule in list_rules(project_root) if rule.status == "active"]
    output_dir = skill_dir(project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    strategy = "inline" if len(rules) <= inline_threshold else "index"

    skill_path = output_dir / "SKILL.md"
    skill_path.write_text(_render_skill_md(rules, strategy), encoding="utf-8")
    catalog_path = _render_catalog(output_dir, rules)

    domain_files: list[Path] = []
    if strategy == "index":
        domain_files = _render_domain_files(output_dir, rules)
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


def _render_skill_md(rules: list[KnowledgeRule], strategy: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    description = (
        "When you work in this project, use these project-approved rules and record new sessions when you learn something reusable."
        if rules
        else "When you work in this project, no approved rules exist yet. Record sessions and run detection to grow the rule set."
    )
    section = _render_inline_section(rules) if strategy == "inline" else _render_index_section(rules)
    return _load_template("skill_main.md.tpl").safe_substitute(
        description=description,
        rules_section=section,
        last_synced=now,
    )


def _render_inline_section(rules: list[KnowledgeRule]) -> str:
    if not rules:
        return "> No active rules yet. Record sessions, run detection, review candidates, and sync again."
    grouped = _group_by_domain(rules)
    parts: list[str] = []
    for domain in sorted(grouped):
        parts.append(f"### {domain}\n")
        for rule in grouped[domain]:
            tags = f" (`{', '.join(rule.tags)}`)" if rule.tags else ""
            parts.append(f"- **{rule.id}** {rule.title}: {rule.statement}{tags}")
        parts.append("")
    return _load_template("skill_inline.md.tpl").safe_substitute(domain_groups="\n".join(parts))


def _render_index_section(rules: list[KnowledgeRule]) -> str:
    grouped = _group_by_domain(rules)
    rows = [f"| {domain} | {len(items)} | {max(item.created_at[:10] for item in items)} |" for domain, items in sorted(grouped.items())]
    return _load_template("skill_index.md.tpl").safe_substitute(domain_table_rows="\n".join(rows))


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


def _render_domain_files(output_dir: Path, rules: list[KnowledgeRule]) -> list[Path]:
    grouped = _group_by_domain(rules)
    domains_dir = output_dir / "domains"
    domains_dir.mkdir(parents=True, exist_ok=True)
    template = _load_template("domain_detail.md.tpl")
    paths: list[Path] = []
    for domain, items in sorted(grouped.items()):
        body_lines: list[str] = []
        for rule in items:
            body_lines.extend(
                [
                    f"## {rule.id}: {rule.title}",
                    f"- Statement: {rule.statement}",
                    f"- Rationale: {rule.rationale}",
                    f"- Tags: {', '.join(rule.tags) if rule.tags else 'none'}",
                    f"- Source sessions: {', '.join(rule.source_session_ids) if rule.source_session_ids else 'none'}",
                    f"- Source candidates: {', '.join(rule.source_candidate_ids) if rule.source_candidate_ids else 'none'}",
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


def _load_template(name: str) -> Template:
    return Template((_TEMPLATES_DIR / name).read_text(encoding="utf-8"))
