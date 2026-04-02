"""Skill 同步引擎。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from string import Template

from self_evolve.config import resolve_template_language, rules_dir, skill_dir
from self_evolve.models import KnowledgeRule
from self_evolve.storage import list_rules

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_SCRIPTS_DIR = Path(__file__).parent / "scripts"
_WINDOWS_RESERVED_BASENAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

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


@dataclass(slots=True, frozen=True)
class FileAction:
    path: Path
    action: str  # "add" | "modify" | "unchanged"


@dataclass(slots=True, frozen=True)
class SyncPlan:
    strategy: str
    previous_strategy: str | None
    rules_count: int
    file_actions: list[FileAction]
    files_to_delete: list[Path]


def sync_skill(
    project_root: Path,
    *,
    inline_threshold: int = 20,
    language: str | None = None,
) -> SyncResult:
    outputs = _compute_sync_outputs(project_root, inline_threshold=inline_threshold, language=language)
    output_dir = skill_dir(project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    for path, content in outputs.file_contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_paths: list[Path] = []
    for dest, source in outputs.script_copies.items():
        try:
            shutil.copy2(source, dest)
            script_paths.append(dest)
        except OSError as e:
            import sys
            print(f"Warning: Failed to copy script {source.name}: {e}", file=sys.stderr)

    _cleanup_stale_domains(output_dir, outputs.strategy, outputs.domain_filename_map)

    skill_path = output_dir / "SKILL.md"
    catalog_path = output_dir / "catalog.json"
    domain_files = [p for p in outputs.file_contents if p.parent.name == "domains"]

    return SyncResult(
        path=skill_path,
        rules_count=outputs.rules_count,
        strategy=outputs.strategy,
        domain_files=sorted(domain_files),
        catalog_path=catalog_path,
        script_paths=script_paths,
    )


def plan_sync(
    project_root: Path,
    *,
    inline_threshold: int = 20,
    language: str | None = None,
) -> SyncPlan:
    """计算 sync 将产生的变更，但不写入任何文件。"""
    outputs = _compute_sync_outputs(project_root, inline_threshold=inline_threshold, language=language)
    output_dir = skill_dir(project_root)
    previous_strategy = _detect_previous_strategy(output_dir)

    file_actions: list[FileAction] = []
    for path, content in outputs.file_contents.items():
        file_actions.append(_classify_file_action(path, content))

    for dest, source in outputs.script_copies.items():
        try:
            source_content = source.read_text(encoding="utf-8")
        except OSError:
            continue
        file_actions.append(_classify_file_action(dest, source_content))

    return SyncPlan(
        strategy=outputs.strategy,
        previous_strategy=previous_strategy,
        rules_count=outputs.rules_count,
        file_actions=sorted(file_actions, key=lambda a: str(a.path)),
        files_to_delete=outputs.stale_files,
    )


def _copy(language: str, key: str) -> str:
    lang_dict = _SYNC_COPY.get(language, _SYNC_COPY["en"])
    return lang_dict.get(key, _SYNC_COPY["en"].get(key, key))


def _load_template(name: str, language: str) -> Template:
    lang_path = _TEMPLATES_DIR / f"{name}.{language}.md.tpl"
    if lang_path.exists():
        return Template(lang_path.read_text(encoding="utf-8"))
    fallback = _TEMPLATES_DIR / f"{name}.en.md.tpl"
    if not fallback.exists():
        raise FileNotFoundError(f"Template not found: {name} (neither {lang_path} nor {fallback})")
    return Template(fallback.read_text(encoding="utf-8"))


def _group_by_domain(rules: list[KnowledgeRule]) -> dict[str, list[KnowledgeRule]]:
    groups: dict[str, list[KnowledgeRule]] = defaultdict(list)
    for rule in rules:
        groups[rule.domain].append(rule)
    return dict(groups)


def _slugify_domain(domain: str) -> str:
    slug = re.sub(r"[^\w]+", "-", domain.strip().lower(), flags=re.UNICODE)
    slug = re.sub(r"-{2,}", "-", slug).strip("-_.")
    return slug or "domain"


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _build_domain_filename_map(rules: list[KnowledgeRule]) -> dict[str, str]:
    domains = sorted({rule.domain for rule in rules})
    domains_by_slug: dict[str, list[str]] = defaultdict(list)
    for domain in domains:
        domains_by_slug[_slugify_domain(domain)].append(domain)

    mapping: dict[str, str] = {}
    for slug, bucket in sorted(domains_by_slug.items()):
        if len(bucket) == 1 and slug not in _WINDOWS_RESERVED_BASENAMES:
            mapping[bucket[0]] = f"{slug}.md"
            continue
        for domain in bucket:
            mapping[domain] = f"{slug}--{_short_hash(domain)}.md"
    return mapping


def _render_skill_md(
    rules: list[KnowledgeRule],
    strategy: str,
    language: str,
    domain_filename_map: dict[str, str],
) -> str:
    description = _copy(language, "description.with_rules" if rules else "description.empty")
    if strategy == "inline":
        rules_section = _render_inline_section(rules, language)
    else:
        rules_section = _render_index_section(rules, language, domain_filename_map)
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


def _parse_timestamp(ts: str) -> datetime:
    """将 ISO 8601 时间戳解析为 datetime，支持 Z 和 +00:00 等格式。"""
    normalized = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min


def _render_index_section(
    rules: list[KnowledgeRule],
    language: str,
    domain_filename_map: dict[str, str],
) -> str:
    groups = _group_by_domain(rules)
    tpl = _load_template("skill_index", language)
    rows: list[str] = []
    for domain in sorted(groups):
        count = len(groups[domain])
        latest_dt = max(_parse_timestamp(r.created_at) for r in groups[domain])
        latest_str = latest_dt.strftime("%Y-%m-%d") if latest_dt != datetime.min else "unknown"
        filename = domain_filename_map[domain]
        rows.append(f"| {domain} | {count} | {latest_str} | [→ details](domains/{filename}) |")
    return tpl.safe_substitute(domain_table_rows="\n".join(rows))


def _build_catalog_payload(rules: list[KnowledgeRule]) -> dict:
    domains: dict[str, int] = defaultdict(int)
    for rule in rules:
        domains[rule.domain] += 1
    return {
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


def _render_catalog(output_dir: Path, rules: list[KnowledgeRule]) -> Path:
    payload = _build_catalog_payload(rules)
    path = output_dir / "catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _render_domain_files(
    output_dir: Path,
    rules: list[KnowledgeRule],
    language: str,
    domain_filename_map: dict[str, str],
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
        path = domains_dir / domain_filename_map[domain]
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def _find_stale_domains(output_dir: Path, strategy: str, domain_filename_map: dict[str, str]) -> list[Path]:
    domains_dir = output_dir / "domains"
    if not domains_dir.exists():
        return []
    if strategy == "inline":
        return sorted(domains_dir.glob("*.md"))
    active_filenames = set(domain_filename_map.values())
    return sorted(p for p in domains_dir.glob("*.md") if p.name not in active_filenames)


def _cleanup_stale_domains(output_dir: Path, strategy: str, domain_filename_map: dict[str, str]) -> None:
    domains_dir = output_dir / "domains"
    if not domains_dir.exists():
        return
    if strategy == "inline":
        shutil.rmtree(domains_dir)
        return
    for path in _find_stale_domains(output_dir, strategy, domain_filename_map):
        path.unlink()


def _sync_scripts(output_dir: Path) -> list[Path]:
    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for source in sorted(_SCRIPTS_DIR.glob("*.py")):
        destination = scripts_dir / source.name
        try:
            shutil.copy2(source, destination)
            paths.append(destination)
        except OSError as e:
            import sys
            print(f"Warning: Failed to copy script {source.name}: {e}", file=sys.stderr)
    return paths


@dataclass(slots=True)
class _SyncOutputs:
    strategy: str
    rules_count: int
    domain_filename_map: dict[str, str]
    file_contents: dict[Path, str]
    script_copies: dict[Path, Path]  # dest → source
    stale_files: list[Path]


def _compute_sync_outputs(
    project_root: Path,
    *,
    inline_threshold: int = 20,
    language: str | None = None,
) -> _SyncOutputs:
    lang = language or resolve_template_language(project_root)
    rules = [r for r in list_rules(project_root) if r.status == "active"]
    output_dir = skill_dir(project_root)

    strategy = "inline" if len(rules) <= inline_threshold else "index"
    domain_filename_map = _build_domain_filename_map(rules) if strategy == "index" else {}

    file_contents: dict[Path, str] = {}

    skill_md = _render_skill_md(rules, strategy, lang, domain_filename_map)
    file_contents[output_dir / "SKILL.md"] = skill_md

    payload = _build_catalog_payload(rules)
    file_contents[output_dir / "catalog.json"] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if strategy == "index":
        groups = _group_by_domain(rules)
        domains_dir = output_dir / "domains"
        tpl = _load_template("domain_detail", lang)
        for domain in sorted(groups):
            lines: list[str] = []
            for rule in groups[domain]:
                lines.append(f"**{rule.id}: {rule.title}**\n")
                lines.append(f"- {_copy(lang, 'domain.statement')}: {rule.statement}")
                lines.append(f"- {_copy(lang, 'domain.rationale')}: {rule.rationale}")
                tags_str = ", ".join(rule.tags) if rule.tags else _copy(lang, "none")
                lines.append(f"- {_copy(lang, 'domain.tags')}: {tags_str}\n")
            content = tpl.safe_substitute(domain=domain, rules_content="\n".join(lines))
            file_contents[domains_dir / domain_filename_map[domain]] = content

    script_copies: dict[Path, Path] = {}
    scripts_dir = output_dir / "scripts"
    for source in sorted(_SCRIPTS_DIR.glob("*.py")):
        script_copies[scripts_dir / source.name] = source

    stale_files = _find_stale_domains(output_dir, strategy, domain_filename_map)

    return _SyncOutputs(
        strategy=strategy,
        rules_count=len(rules),
        domain_filename_map=domain_filename_map,
        file_contents=file_contents,
        script_copies=script_copies,
        stale_files=stale_files,
    )


def _detect_previous_strategy(output_dir: Path) -> str | None:
    skill_md = output_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    domains_dir = output_dir / "domains"
    if domains_dir.is_dir() and any(domains_dir.glob("*.md")):
        return "index"
    return "inline"


def _classify_file_action(path: Path, new_content: str) -> FileAction:
    if not path.exists():
        return FileAction(path=path, action="add")
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        return FileAction(path=path, action="add")
    if existing == new_content:
        return FileAction(path=path, action="unchanged")
    return FileAction(path=path, action="modify")
