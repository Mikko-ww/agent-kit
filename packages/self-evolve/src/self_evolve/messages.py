"""CLI 翻译。"""

from __future__ import annotations

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "app.help": "Self-evolve: project-level knowledge rule management.",
        "metadata.help": "Output plugin metadata as JSON.",
        "init.help": "Initialize self-evolve for this project.",
        "init.language.prompt": "Select template language (en / zh-CN)",
        "init.completed": "Initialized successfully.",
        "sync.help": "Sync active rules to the Skill output.",
        "sync.completed": "Sync completed: {rules_count} active rules, strategy={strategy}.",
        "sync.dry_run.help": "Preview changes without writing files.",
        "sync.dry_run.header": "Dry run — no files will be written.",
        "sync.dry_run.strategy": "Strategy: {strategy} (threshold={threshold})",
        "sync.dry_run.strategy_change": "Strategy change: {previous} → {current}",
        "sync.dry_run.rules": "Rules: {count} active",
        "sync.dry_run.files_header": "File changes:",
        "sync.dry_run.no_changes": "No changes needed.",
        "sync.dry_run.deletes_header": "Files to delete:",
        "sync.dry_run.no_deletes": "No files to delete.",
        "status.help": "Show self-evolve status.",
        "status.rules": "Rules: total={total}, {counts}",
        "status.domains": "Domains: {domains}",
        "status.strategy": "Strategy: {strategy} (threshold={threshold})",
        "status.last_synced": "Last synced: {last_synced}",
        "status.needs_sync": "Needs sync: {needs_sync}",
        "yes": "yes",
        "no": "no",
        "warning.not_initialized": "Project not initialized. Run 'agent-kit self-evolve init' first.",
        "warning.already_initialized": "Already initialized at {path}.",
        "warning.not_found": "{entity} not found: {id}",
    },
    "zh-CN": {
        "app.help": "Self-evolve：项目级知识规则管理。",
        "metadata.help": "以 JSON 格式输出插件元信息。",
        "init.help": "为当前项目初始化 self-evolve。",
        "init.language.prompt": "选择模板语言 (en / zh-CN)",
        "init.completed": "初始化完成。",
        "sync.help": "将 active 规则同步到 Skill 输出。",
        "sync.completed": "同步完成：{rules_count} 条 active 规则，策略={strategy}。",
        "sync.dry_run.help": "预览变更，不写入文件。",
        "sync.dry_run.header": "模拟运行 — 不会写入任何文件。",
        "sync.dry_run.strategy": "策略：{strategy}（阈值={threshold}）",
        "sync.dry_run.strategy_change": "策略变更：{previous} → {current}",
        "sync.dry_run.rules": "规则：{count} 条 active",
        "sync.dry_run.files_header": "文件变更：",
        "sync.dry_run.no_changes": "无需变更。",
        "sync.dry_run.deletes_header": "待删除文件：",
        "sync.dry_run.no_deletes": "无文件待删除。",
        "status.help": "显示 self-evolve 状态。",
        "status.rules": "规则：总数={total}，{counts}",
        "status.domains": "领域分布：{domains}",
        "status.strategy": "策略：{strategy}（阈值={threshold}）",
        "status.last_synced": "上次同步：{last_synced}",
        "status.needs_sync": "需要同步：{needs_sync}",
        "yes": "是",
        "no": "否",
        "warning.not_initialized": "项目未初始化。请先运行 'agent-kit self-evolve init'。",
        "warning.already_initialized": "已在 {path} 初始化过。",
        "warning.not_found": "未找到{entity}：{id}",
    },
}


def translate(language: str, key: str, **kwargs: object) -> str:
    lang_dict = _MESSAGES.get(language, _MESSAGES["en"])
    template = lang_dict.get(key, _MESSAGES["en"].get(key, key))
    if kwargs:
        return template.format(**kwargs)
    return template
