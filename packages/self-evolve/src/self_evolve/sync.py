"""将推广规则同步到各 agent 的 skill / 指令文件。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from self_evolve.models import PromotedRule

# 标记块的起止标记
_BLOCK_START = "<!-- self-evolve:start -->"
_BLOCK_END = "<!-- self-evolve:end -->"


@dataclass(slots=True, frozen=True)
class SyncResult:
    target: str
    path: Path
    rules_count: int


def sync_to_targets(
    project_root: Path,
    rules: list[PromotedRule],
    targets: list[str],
) -> list[SyncResult]:
    """将规则同步到指定的 agent targets。"""
    results: list[SyncResult] = []
    for target in targets:
        renderer = _RENDERERS.get(target)
        if renderer is None:
            continue
        result = renderer(project_root, rules)
        results.append(result)
    return results


def sync_cursor(project_root: Path, rules: list[PromotedRule]) -> SyncResult:
    """生成 .cursor/rules/self-evolve.mdc 文件。"""
    path = project_root / ".cursor" / "rules" / "self-evolve.mdc"
    content = _render_cursor(rules)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return SyncResult(target="cursor", path=path, rules_count=len(rules))


def sync_copilot(project_root: Path, rules: list[PromotedRule]) -> SyncResult:
    """管理 .github/copilot-instructions.md 中的 self-evolve 块。"""
    path = project_root / ".github" / "copilot-instructions.md"
    block = _render_copilot_block(rules)
    _upsert_block(path, block)
    return SyncResult(target="copilot", path=path, rules_count=len(rules))


def sync_codex(project_root: Path, rules: list[PromotedRule]) -> SyncResult:
    """管理 .codex/AGENTS.md 中的 self-evolve 块。"""
    path = project_root / ".codex" / "AGENTS.md"
    block = _render_codex_block(rules)
    _upsert_block(path, block)
    return SyncResult(target="codex", path=path, rules_count=len(rules))


# ── Cursor 渲染 ──────────────────────────────────────────────────────


def _render_cursor(rules: list[PromotedRule]) -> str:
    """渲染 Cursor Rules MDC 格式。"""
    lines = [
        "---",
        "description: Project-specific rules auto-evolved from development experience",
        "globs:",
        "alwaysApply: true",
        "---",
        "",
        "# Self-Evolved Project Rules",
        "",
    ]

    if rules:
        for i, rule in enumerate(rules, 1):
            lines.append(f"{i}. **[{rule.domain}]** {rule.rule}")
        lines.append("")

    lines.extend(_capture_instructions())
    return "\n".join(lines)


# ── Copilot 渲染 ─────────────────────────────────────────────────────


def _render_copilot_block(rules: list[PromotedRule]) -> str:
    """渲染 Copilot 指令中的 self-evolve 块（含标记）。"""
    lines = [
        _BLOCK_START,
        "",
        "## Self-Evolved Project Rules",
        "",
    ]

    if rules:
        for i, rule in enumerate(rules, 1):
            lines.append(f"{i}. **[{rule.domain}]** {rule.rule}")
        lines.append("")

    lines.extend(_capture_instructions())
    lines.append(_BLOCK_END)
    return "\n".join(lines)


# ── Codex 渲染 ───────────────────────────────────────────────────────


def _render_codex_block(rules: list[PromotedRule]) -> str:
    """渲染 Codex AGENTS.md 中的 self-evolve 块（含标记）。"""
    lines = [
        _BLOCK_START,
        "",
        "## Self-Evolved Project Rules",
        "",
    ]

    if rules:
        for i, rule in enumerate(rules, 1):
            lines.append(f"{i}. **[{rule.domain}]** {rule.rule}")
        lines.append("")

    lines.extend(_capture_instructions())
    lines.append(_BLOCK_END)
    return "\n".join(lines)


# ── 共享工具 ─────────────────────────────────────────────────────────


def _capture_instructions() -> list[str]:
    """生成嵌入到 agent 指令文件中的捕获引导。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
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
    ]


def _upsert_block(path: Path, block: str) -> None:
    """在文件中插入或更新标记块。文件不存在则创建。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = ""

    start_idx = content.find(_BLOCK_START)
    end_idx = content.find(_BLOCK_END)

    if start_idx != -1 and end_idx != -1:
        # 替换现有块
        end_idx += len(_BLOCK_END)
        new_content = content[:start_idx] + block + content[end_idx:]
    else:
        # 追加到文件末尾
        if content and not content.endswith("\n"):
            content += "\n"
        if content:
            content += "\n"
        new_content = content + block + "\n"

    path.write_text(new_content, encoding="utf-8")


_RENDERERS = {
    "cursor": sync_cursor,
    "copilot": sync_copilot,
    "codex": sync_codex,
}
