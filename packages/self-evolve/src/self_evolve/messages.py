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
        "status.help": "Show self-evolve status.",
        "status.rules": "Rules: total={total}, {counts}",
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
        "status.help": "显示 self-evolve 状态。",
        "status.rules": "规则：总数={total}，{counts}",
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
