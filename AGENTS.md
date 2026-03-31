# Agent Kit 仓库说明

本文件面向整个仓库中的 agent，负责定义全局规则、提供项目总体架构摘要，并把更具体的约束导航到对应目录下的 `AGENTS.md`。

## 1. 全局规则

- 所有 agent 与用户的交流默认使用中文。
- Git 提交信息必须使用中文。
- Markdown 文件、设计文档、说明文档以中文为主。
- 文档中的代码、命令、字段名、包名、类名、函数名、专用技术名词保持英文。
- 代码中的注释与 `log` 默认以中文为主；若属于稳定协议字段或外部接口，字段名保持英文。
- `agent-kit` 及第一方插件的 CLI 默认语言是英文，当前支持 `en` 与 `zh-CN`。
- CLI 语言决议顺序固定为：`AGENT_KIT_LANG` 环境变量 > `~/.config/agent-kit/config.jsonc` 中的全局 `language` 配置 > 系统语言环境变量 > 英文默认值。
- 当 core 通过 `agent-kit <plugin-id> ...` 启动插件时，插件必须遵从 core 透传的最终语言，不得自行偏离。
- 子目录中的 `AGENTS.md` 默认继承本文件规则；子级只补充和细化，不覆盖本文件中的全局规则。
- 当 agent 的改动涉及 `packages/<plugin>/` 下任意第一方插件时，不能只停在功能提交；功能提交完成后，必须继续补做插件发布流程。
- 上述插件发布补流程必须使用项目内 skill `./.agents/skills/plugin-release-followup/`，不得由 agent 自行省略、替换或只执行其中一部分。
- 当 agent 的改动涉及任意非 `packages/<plugin>/` 的仓库文件时，不能只停在功能提交；功能提交完成后，必须继续补做一次 core 版本升级流程。
- 上述非插件改动的 core 升版补流程必须使用项目内 skill `./.agents/skills/core-release-followup/`，不得由 agent 自行省略、替换或只执行其中一部分。
- 非插件改动的 core 升版补动作固定通过 `./scripts/release/ak-core-release.sh` 完成，不得手工模拟或绕过该入口。

## 2. 变更一致性要求

- 当用户当前需求与现有架构、既有设计思路、目录分层规则，或任一层级 `AGENTS.md` 中记录的约束不一致时，agent 不得直接实施。
- 遇到上述冲突时，agent 必须先明确告知用户冲突点、潜在影响和可选调整方向，待用户明确确认变更后再继续实施。
- 若用户确认变更，agent 在实施完成后必须同步更新受影响层级的 `AGENTS.md`，确保文档约束、目录说明与实际实现保持一致。
- 对于涉及架构偏移、设计方向调整或文档约束变更的需求，若未取得用户明确确认，agent 不得自行假设并推进实施。
- 当 agent 新增功能、修改功能、调整命令、变更配置、改变目录结构、更新插件协议，或修改任何用户可见行为时，必须同步检查对应层级的 `README.md` 是否需要更新。
- 如果相关 `README.md` 已因本次改动而失效或信息不完整，agent 必须在同一次任务中一并完成更新，不得只改实现而遗漏用户文档。

## 3. 项目总体架构摘要

`agent-kit` 是一个可扩展的 Python CLI 平台，统一入口是 `agent-kit`。

- Core 负责官方插件注册表、插件安装/更新/卸载、版本校验和命令转发。
- Core 当前支持 `pypi`、`git`、`wheel` 三种官方插件安装来源，其中 `wheel` 需要先下载并校验 `sha256`。
- 插件运行在各自独立环境中，core 通过子进程调用插件统一入口 `agent-kit-plugin`。
- 当前第一方插件包括：
  - `skills-link`：把本地 skills 目录按目录粒度链接到目标目录。
  - `opencode-env-switch`：通过 shell 环境变量切换 OpenCode profile。

## 4. 顶层目录导航

- [src/agent_kit](src/agent_kit)：core 实现
  具体约束见 [src/agent_kit/AGENTS.md](src/agent_kit/AGENTS.md)
- [packages](packages)：所有插件目录
  共享规则见 [packages/AGENTS.md](packages/AGENTS.md)
- [packages/skills-link](packages/skills-link)：当前第一方插件
  插件自身规则见 [packages/skills-link/AGENTS.md](packages/skills-link/AGENTS.md)
- [packages/opencode-env-switch](packages/opencode-env-switch)：OpenCode profile 切换插件
  插件自身规则见 [packages/opencode-env-switch/AGENTS.md](packages/opencode-env-switch/AGENTS.md)
- [scripts](scripts)：开发与发布辅助脚本
  具体约束见 [scripts/AGENTS.md](scripts/AGENTS.md)
- [docs](docs)：设计文档与实施计划

## 5. AGENTS 分层规则

- 根目录 `AGENTS.md` 只放全局规则、总体架构摘要和导航。
- `src/agent_kit/AGENTS.md` 只放 core 相关约束。
- `packages/AGENTS.md` 只放插件共享协议与新增插件约束。
- `packages/<plugin>/AGENTS.md` 只放单个插件自己的业务规则。

## 6. 工作建议

- 先确认当前修改落在 core 还是某个插件目录。
- 进入具体目录后，优先阅读该目录最近的 `AGENTS.md`。
- 修改协议、目录结构或命令形态时，同步更新对应层级的 `AGENTS.md` 与测试。
