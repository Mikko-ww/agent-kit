from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "app.help": "Import the planning-files skill into supported agent platforms.",
        "metadata.help": "Print plugin metadata as JSON.",
        "import.help": "Import platform resources for planning-files.",
        "status.help": "Inspect planning-files installation status.",
        "option.platform": "Target platform: codex, cursor, opencode, generic, or all.",
        "option.language": "Skill language: en or zh-CN. Defaults to the resolved agent-kit language.",
        "option.scope": "Install scope: project or global.",
        "option.dry_run": "Preview changes without writing files.",
        "option.force": "Overwrite unmanaged files in the planning-files skill directory.",
        "import.header": "Import {platform} {scope} -> {path}",
        "status.installed": "{platform} {scope}: installed language={language} path={path}",
        "status.missing": "{platform} {scope}: missing path={path}",
        "warning.codex_hooks": "Codex hooks require codex_hooks = true under [features] in ~/.codex/config.toml.",
        "action.line": "{action}: {path}",
        "error": "Error: {message}",
    },
    "zh-CN": {
        "app.help": "导入 planning-files skill 到受支持的 Agent 平台。",
        "metadata.help": "以 JSON 输出插件元数据。",
        "import.help": "导入平台资源。",
        "status.help": "查看 planning-files 安装状态。",
        "option.platform": "目标平台：codex、cursor、opencode、generic 或 all。",
        "option.language": "技能语言：en 或 zh-CN。默认使用 agent-kit 已决议语言。",
        "option.scope": "安装范围：project 或 global。",
        "option.dry_run": "预览变更，不写入文件。",
        "option.force": "覆盖 planning-files skill 目录中的非托管文件。",
        "import.header": "导入 {platform} {scope} -> {path}",
        "status.installed": "{platform} {scope}: 已安装 language={language} path={path}",
        "status.missing": "{platform} {scope}: 未安装 path={path}",
        "warning.codex_hooks": "Codex hooks 需要在 ~/.codex/config.toml 的 [features] 下启用 codex_hooks = true。",
        "action.line": "{action}: {path}",
        "error": "错误：{message}",
    },
}


def translate(lang: str, key: str, **kwargs: object) -> str:
    catalog = MESSAGES.get(lang, MESSAGES["en"])
    template = catalog.get(key, MESSAGES["en"].get(key, key))
    return template.format(**kwargs)
