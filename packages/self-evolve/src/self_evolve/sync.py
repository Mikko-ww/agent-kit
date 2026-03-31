"""将推广规则同步为统一的 Agent Skill 文件（.agents/skills/self-evolve/SKILL.md）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from self_evolve.config import skill_dir
from self_evolve.models import PromotedRule


@dataclass(slots=True, frozen=True)
class SyncResult:
    path: Path
    rules_count: int


def sync_skill(
    project_root: Path,
    rules: list[PromotedRule],
) -> SyncResult:
    """将规则同步到 .agents/skills/self-evolve/SKILL.md。"""
    target = skill_dir(project_root)
    target.mkdir(parents=True, exist_ok=True)
    path = target / "SKILL.md"
    content = _render_skill(rules)
    path.write_text(content, encoding="utf-8")
    return SyncResult(path=path, rules_count=len(rules))


# ── SKILL.md 渲染 ────────────────────────────────────────────────────


def _render_skill(rules: list[PromotedRule]) -> str:
    """渲染 SKILL.md 格式。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# Self-Evolved Project Rules",
        "",
    ]

    if rules:
        for i, rule in enumerate(rules, 1):
            lines.append(f"{i}. **[{rule.domain}]** {rule.rule}")
        lines.append("")

    lines.extend([
        "## Self-Evolution Integration",
        "",
        "When you discover a recurring pattern, a useful convention, or an important",
        "lesson during this session, capture it so the project can evolve:",
        "",
        "```bash",
        'agent-kit self-evolve capture \\',
        '  --summary "Brief description of the learning" \\',
        '  --domain "debugging|testing|architecture|performance|security|style" \\',
        '  --pattern-key "unique-pattern-identifier" \\',
        '  --task-id "current-task-id"',
        "```",
        "",
        "After capturing several learnings, run the evolution cycle:",
        "",
        "```bash",
        "agent-kit self-evolve evolve",
        "```",
        "",
        f"_Last synced: {now}_",
        "",
    ])
    return "\n".join(lines)
