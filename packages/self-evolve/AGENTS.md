# self-evolve 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `self-evolve` 自身约束。

## 1. 插件目标

`self-evolve` v5 是一个项目级知识规则管理插件，采用 Rule-only 极简架构。Agent 通过 Skill 中嵌入的反思注入指令和零依赖脚本直接操作 Rule，无中间实体。

固定流程：

```text
Agent 反思 → 脚本写入 Rule → sync → SKILL.md
```

## 2. 对外命令

- `agent-kit self-evolve init`
- `agent-kit self-evolve sync`
- `agent-kit self-evolve status`

v5 不提供 session/candidate/rule/detect 子命令。Rule CRUD 由 `scripts/` 目录下的零依赖 Python 脚本完成。

## 3. 配置

配置文件：

- `<project-root>/.agents/self-evolve/config.jsonc`

当前有效字段：

- `plugin_id`
- `config_version`
- `language`
- `inline_threshold`

固定约束：

- `config_version` 当前为 `5`
- `init` 时必须显式选择模板语言，并写入 `config.jsonc` 的 `language`
- 模板语言决议顺序固定为：项目配置 `language` > `AGENT_KIT_LANG` > `en`
- CLI 文案语言继续走 core 决议链，不能被项目模板语言字段覆盖

## 4. 数据存储

项目级数据目录固定为：

- `<project-root>/.agents/self-evolve/rules/`

规则：

- `rule` 按单文件 JSON 存储（`R-NNN.json`）
- 不允许回退到聚合文件

## 5. 核心概念

- **Rule**：已批准、可同步到 Skill 的正式规则
- **脚本层**：`scripts/` 目录下的零依赖 Python 脚本，由 Agent 在 Skill 指引下调用

## 6. Skill 同步

Skill 输出目录固定为：

- `.agents/skills/self-evolve/SKILL.md`
- `.agents/skills/self-evolve/catalog.json`
- `.agents/skills/self-evolve/scripts/add_rule.py`
- `.agents/skills/self-evolve/scripts/edit_rule.py`
- `.agents/skills/self-evolve/scripts/retire_rule.py`
- `.agents/skills/self-evolve/scripts/list_rules.py`
- `.agents/skills/self-evolve/scripts/find_rules.py`
- `.agents/skills/self-evolve/domains/*.md`（仅 index 策略）

同步约束：

- 只同步 `status=active` 的正式 `rule`
- 继续保留 `inline/index` 双策略
- `SKILL.md` 包含反思注入指令，引导 Agent 从对话上下文中提取结构化知识并调用脚本写入规则
- `SKILL.md`、索引页和 domain 详情页必须按模板语言生成，并与项目配置保持同步

## 7. 修改本插件时重点验证

- `init` 是否正确创建 v5 目录布局、提示选择模板语言并写入配置
- `sync` 是否只消费 active rule，并按配置语言生成正确的模板与 `catalog.json`
- `catalog.json` 版本是否为 1，规则条目是否不包含 `source_sessions`、`source_candidates`
- 五个脚本是否正确复制到 Skill 输出目录
- 脚本是否能从 `.agents/skills/self-evolve/scripts/` 正确推算 `rules/` 目录
- 反思注入模板是否引导 Agent 先查重再写入
- 中英文 `--help`、warning/error、状态输出是否一致

相关测试：

- [tests/test_config.py](tests/test_config.py)
- [tests/test_models.py](tests/test_models.py)
- [tests/test_storage.py](tests/test_storage.py)
- [tests/test_scripts.py](tests/test_scripts.py)
- [tests/test_sync.py](tests/test_sync.py)
