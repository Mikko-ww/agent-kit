"""v5 Skill 同步引擎。"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from string import Template

from self_evolve.config import resolve_template_language, rules_dir, skill_dir
from self_evolve.models import KnowledgeRule
from self_evolve.storage import list_rules

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_SCRIPTS_DIR = Path(__file__).parent / "scripts"

_SYNC_COPY: dict[str, dict[str, str]] = {
    "en": {
        "description.with_rules": "When you work in this project, follow these approved rules. Use the reflection workflow below to add new rules when you learn something reusable.",
        "description.empty": "When you work in this project, no approved rules exist yet. Use the reflection workflow below to start building the rule set.",
        "no_active_rules": "> No active rules yet. Use the reflection workflow to add rules, then run `agent-kit self-evolve sync`.",
        "domain.statement": "Statement",
        "domain.rationale": "Rationale",
        "domain.tags": "Tags",
        "none": "none",
    },
    "zh-CN": {
        "description.with_rules": "当你在此项目中工作时，请优先遵循这些已批准的项目规则。如果学到可复用经验，请使用下方的反思注入流程新增规则。",
        "description.empty": "当你在此项目中工作时，当前还没有已批准规则。请使用下方的反思注入流程开始沉淀规则集。",
        "no_active_rules": "> 当前还没有 active 规则。请使用反思注入流程新增规则，然后运行 `agent-kit self-evolve sync`。",
        "domain.statement": "规则描述",
        "domain.rationale": "原因",
        "domain.tags": "标签",
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
    script_paths: list[Path] = field(default_factory=list)


def sync_skill(
    project_root: Path,
    *,
    inline_threshold: int = 20,
    language: str | None = None,
) -> SyncResult:
    lang = language or resolve_template_language(project_root)
    rules = [r for r in list_rules(project_root) if r.status == "active"]
    output_dir = skill_dir(project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    strategy = "inline" if len(rules) <= inline_threshold else "index"

    skill_md = _render_skill_md(rules, strategy, lang)
    skill_path = output_dir / "SKILL.md"
    skill_path.write_text(skill_md, encoding="utf-8")

    catalog_path = _render_catalog(output_dir, rules)
    domain_files = _render_domain_files(output_dir, rules, lang) if strategy == "index" else []
    _cleanup_stale_domains(output_dir, rules, strategy)
    script_paths = _sync_scripts(output_dir)

    return SyncResult(
        path=skill_path,
        rules_count=len(rules),
        strategy=strategy,
        domain_files=domain_files,
        catalog_path=catalog_path,
        script_paths=script_paths,
    )


def _copy(language: str, key: str) -> str:
    lang_dict = _SYNC_COPY.get(language, _SYNC_COPY["en"])
    return lang_dict.get(key, _SYNC_COPY["en"].get(key, key))


def _load_template(name: str, language: str) -> Template:
    lang_path = _TEMPLATES_DIR / f"{name}.{language}.md.tpl"
    if lang_path.exists():
        return Template(lang_path.read_text(encoding="utf-8"))
    fallback = _TEMPLATES_DIR / f"{name}.en.md.tpl"
    return Template(fallback.read_text(encoding="utf-8"))


def _group_by_domain(rules: list[KnowledgeRule]) -> dict[str, list[KnowledgeRule]]:
    groups: dict[str, list[KnowledgeRule]] = defaultdict(list)
    for rule in rules:
        groups[rule.domain].append(rule)
    return dict(groups)


def _render_skill_md(rules: list[KnowledgeRule], strategy: str, language: str) -> str:
    description = _copy(language, "description.with_rules" if rules else "description.empty")
    if strategy == "inline":
        rules_section = _render_inline_section(rules, language)
    else:
        rules_section = _render_index_section(rules, language)
    tpl = _load_template("skill_main", language)
    return tpl.safe_substitute(
        description=description,
        rules_section=rules_section,
        last_synced=str(date.today()),
    )


def _render_inline_section(rules: list[KnowledgeRule], language: str) -> str:
    if not rules:
        return _copy(language, "no_active_rules")
    groups = _group_by_domain(rules)
    tpl = _load_template("skill_inline", language)
    parts: list[str] = []
    for domain in sorted(groups):
        lines = [f"### {domain}\n"]
        for rule in groups[domain]:
            lines.append(f"**{rule.id}: {rule.title}**\n")
            lines.append(f"- {_copy(language, 'domain.statement')}: {rule.statement}")
            lines.append(f"- {_copy(language, 'domain.rationale')}: {rule.rationale}")
            tags_str = ", ".join(rule.tags) if rule.tags else _copy(language, "none")
            lines.append(f"- {_copy(language, 'domain.tags')}: {tags_str}\n")
        parts.append("\n".join(lines))
    return tpl.safe_substitute(domain_groups="\n".join(parts))


def _render_index_section(rules: list[KnowledgeRule], language: str) -> str:
    groups = _group_by_domain(rules)
    tpl = _load_template("skill_index", language)
    rows: list[str] = []
    for domain in sorted(groups):
        count = len(groups[domain])
        latest = max(r.created_at for r in groups[domain])
        rows.append(f"| {domain} | {count} | {latest[:10]} | [→ details](domains/{domain}.md) |")
    return tpl.safe_substitute(domain_table_rows="\n".join(rows))


def _render_catalog(output_dir: Path, rules: list[KnowledgeRule]) -> Path:
    domains: dict[str, int] = defaultdict(int)
    for rule in rules:
        domains[rule.domain] += 1
    payload = {
        "version": 1,
        "last_synced": str(date.today()),
        "summary": {
            "total_rules": len(rules),
            "domains": dict(sorted(domains.items())),
        },
        "rules": [
            {
                "id": rule.id,
                "title": rule.title,
                "statement": rule.statement,
                "rationale": rule.rationale,
                "domain": rule.domain,
                "tags": list(rule.tags),
                "created_at": rule.created_at,
                "revision_of": rule.revision_of,
            }
            for rule in rules
        ],
    }
    path = output_dir / "catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _render_domain_files(
    output_dir: Path, rules: list[KnowledgeRule], language: str
) -> list[Path]:
    groups = _group_by_domain(rules)
    domains_dir = output_dir / "domains"
    domains_dir.mkdir(parents=True, exist_ok=True)
    tpl = _load_template("domain_detail", language)
    paths: list[Path] = []
    for domain in sorted(groups):
        lines: list[str] = []
        for rule in groups[domain]:
            lines.append(f"**{rule.id}: {rule.title}**\n")
            lines.append(f"- {_copy(language, 'domain.statement')}: {rule.statement}")
            lines.append(f"- {_copy(language, 'domain.rationale')}: {rule.rationale}")
            tags_str = ", ".join(rule.tags) if rule.tags else _copy(language, "none")
            lines.append(f"- {_copy(language, 'domain.tags')}: {tags_str}\n")
        content = tpl.safe_substitute(domain=domain, rules_content="\n".join(lines))
        path = domains_dir / f"{domain}.md"
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def _cleanup_stale_domains(
    output_dir: Path, rules: list[KnowledgeRule], strategy: str
) -> None:
    domains_dir = output_dir / "domains"
    if not domains_dir.exists():
        return
    if strategy == "inline":
        shutil.rmtree(domains_dir)
        return
    active_domains = {r.domain for r in rules}
    for path in domains_dir.glob("*.md"):
        if path.stem not in active_domains:
            path.unlink()


def _sync_scripts(output_dir: Path) -> list[Path]:
    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for source in sorted(_SCRIPTS_DIR.glob("*.py")):
        destination = scripts_dir / source.name
        shutil.copy2(source, destination)
        paths.append(destination)
    return paths
