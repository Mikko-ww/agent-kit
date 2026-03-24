# Agent Kit v1 总入口与 `skills-link` Toolkit 设计

## 摘要

- 目标是交付一个可扩展的 Python CLI 平台：用户安装后直接运行 `agent-kit <toolkit> <action>`，toolkit 独立安装并自动挂载到总入口。
- 仓库采用 `uv` 单仓多包结构，v1 先实现两个包：核心包 `agent-kit` 与首个真实 toolkit 包 `skills-link`。
- 该版本优先内部团队使用，先把插件边界、交互流程和测试基线做扎实。

## 架构

- 仓库根包 `agent-kit` 是 workspace root，同时也是 CLI 核心包。
- `packages/skills-link` 是首个独立 toolkit 包，通过 Python entry points 自动暴露给核心包。
- 根命令固定为 `agent-kit <toolkit> <action>`。
- toolkit 统一实现 `Toolkit` 契约：声明名称、帮助文本、版本，以及构建 Typer 子命令应用的入口。

## Core 职责

- 提供 `agent-kit` console script。
- 扫描 `agent_kit.toolkits` entry point group，动态发现 toolkit。
- 注入最小公共上下文：日志器、用户配置目录、当前工作目录、统一交互接口。
- 某个 toolkit 导入失败时保留 CLI 的部分可用性，并在帮助输出中展示失败信息。

## `skills-link` Toolkit

- 首个 toolkit 名称固定为 `skills-link`。
- 通过用户级配置文件保存源 skills 目录与目标目录。
- 一个 skill 的识别单位是源目录下一层直接子目录，且该目录必须包含 `SKILL.md`。
- `link` 与 `unlink` 都以 skill 目录为单位进行交互式多选。
- 不覆盖冲突目标，不做自动备份，不处理 Windows。

## 命令

- `agent-kit skills-link init`
- `agent-kit skills-link list`
- `agent-kit skills-link link`
- `agent-kit skills-link unlink`
- `agent-kit skills-link status`

## 运行时规则

- 未完成配置时，执行 `list`、`link`、`unlink`、`status` 自动进入 `init` 引导。
- 目标位置存在同名文件、目录或指向其他位置的软链接时，一律判定为冲突并拒绝覆盖。
- `unlink` 仅删除指向当前源目录的软链接。

## 测试要求

- core 测试：toolkit 发现成功、单个 toolkit 失败不影响其他 toolkit、帮助输出展示失败原因。
- `skills-link` 测试：配置读写、路径校验、状态判定、真实软链接创建、冲突拒绝、断裂链接识别、外部软链接保护。
- CLI 测试：初始化、自动引导、交互选择、状态输出。
