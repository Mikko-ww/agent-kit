# self-evolve 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `self-evolve` 自身约束。

## 1. 插件目标

`self-evolve` v4 是一个项目级知识流水线插件，用于把结构化 `session` 检测成 `candidate`，再沉淀为正式 `rule`，最后同步为统一 Skill 输出给所有 Agent 消费。

固定流程：

```text
session -> candidate -> rule -> skill sync
```

## 2. 对外命令

- `agent-kit self-evolve init`
- `agent-kit self-evolve session record`
- `agent-kit self-evolve detect run`
- `agent-kit self-evolve candidate list`
- `agent-kit self-evolve candidate show`
- `agent-kit self-evolve candidate accept`
- `agent-kit self-evolve candidate reject`
- `agent-kit self-evolve candidate edit`
- `agent-kit self-evolve rule add`
- `agent-kit self-evolve rule list`
- `agent-kit self-evolve rule show`
- `agent-kit self-evolve rule edit`
- `agent-kit self-evolve rule retire`
- `agent-kit self-evolve sync`
- `agent-kit self-evolve status`

旧命令 `capture`、`list`、`analyze`、`promote`、`evolve`、`search` 已全部废弃，不允许继续恢复兼容层。

## 3. 配置

配置文件：

- `<project-root>/.agents/self-evolve/config.jsonc`

当前有效字段：

- `plugin_id`
- `config_version`
- `language`
- `auto_accept_enabled`
- `auto_accept_min_confidence`
- `inline_threshold`

固定约束：

- `config_version` 当前为 `4`
- `init` 时必须显式选择模板语言，并写入 `config.jsonc` 的 `language`
- 模板语言决议顺序固定为：项目配置 `language` > `AGENT_KIT_LANG` > `en`
- CLI 文案语言继续走 core 决议链，不能被项目模板语言字段覆盖
- 旧字段 `promotion_threshold`、`promotion_window_days`、`min_task_count`、`auto_promote` 已废弃
- 检测到旧配置或旧数据布局时必须直接报错，不得隐式迁移

## 4. 数据存储

项目级数据目录固定为：

- `<project-root>/.agents/self-evolve/sessions/`
- `<project-root>/.agents/self-evolve/candidates/`
- `<project-root>/.agents/self-evolve/rules/`
- `<project-root>/.agents/self-evolve/indexes/`

规则：

- `session`、`candidate`、`rule` 统一按单文件 JSON 存储
- `session` 是主输入，默认不可原地改写
- `candidate` 和 `rule` 的状态更新后必须刷新索引
- 不允许回退到 `learnings/` 或 `rules.jsonc` 聚合文件

## 5. 核心概念

- **Session**：一次任务会话的结构化事实记录
- **Candidate**：由检测器生成的待确认知识候选
- **Rule**：已批准、可同步到 Skill 的正式规则
- **Index**：维护 session/candidate/rule 追溯与查找关系
- **Auto Accept**：可选自动生效能力，默认关闭

## 6. Skill 同步

Skill 输出目录固定为：

- `.agents/skills/self-evolve/SKILL.md`
- `.agents/skills/self-evolve/catalog.json`
- `.agents/skills/self-evolve/scripts/find_rules.py`
- `.agents/skills/self-evolve/domains/*.md`（仅 index 策略）

同步约束：

- 只同步 `status=active` 的正式 `rule`
- 不同步 `candidate`
- 不同步 `session`
- 继续保留 `inline/index` 双策略
- `SKILL.md`、索引页和 domain 详情页必须按模板语言生成，并与项目配置保持同步

## 7. 修改本插件时重点验证

- `init` 是否正确创建 v4 目录布局、提示选择模板语言并写入配置
- `session record` 是否正确写入结构化 session
- `detect run` 是否只处理未处理 session，并正确生成或合并 candidate
- `candidate accept/reject/edit` 是否正确刷新索引与状态
- `rule add/edit/retire` 是否正确影响 active rule 集合
- `sync` 是否只消费 active rule，并按配置语言生成正确的模板与 `catalog.json`
- `find_rules.py` 是否能基于 v2 catalog 正常检索
- 中英文 `--help`、warning/error、状态输出是否一致
- 发现旧布局时是否直接报错且不做迁移

相关测试：

- [tests/test_config.py](tests/test_config.py)
- [tests/test_models.py](tests/test_models.py)
- [tests/test_storage.py](tests/test_storage.py)
- [tests/test_detector.py](tests/test_detector.py)
- [tests/test_cli_session.py](tests/test_cli_session.py)
- [tests/test_cli_candidate_rule.py](tests/test_cli_candidate_rule.py)
- [tests/test_sync.py](tests/test_sync.py)
