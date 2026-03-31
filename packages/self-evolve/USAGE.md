# self-evolve 使用指南

## 概述

`self-evolve` v5 采用 Rule-only 极简架构，帮助你把项目中的可复用知识沉淀为结构化规则。

核心流程：

```text
Agent 反思 → 脚本写入 Rule → sync → SKILL.md → Agent 消费规则
```

## 1. 初始化项目

```bash
cd your-project
agent-kit self-evolve init
```

初始化时会提示选择模板语言（`en` 或 `zh-CN`）。如果设置了 `AGENT_KIT_LANG` 环境变量，会自动使用该值。

## 2. 通过 Skill 触发反思注入

`SKILL.md` 中包含反思注入指令。当 Agent 加载了这个 Skill 后，你可以要求 Agent：

- "总结本次调试经验"
- "提取一条规则"
- "把这个教训记录下来"

Agent 会按照 Skill 中的步骤：
1. 先检查是否已有相似规则
2. 从对话上下文中提取结构化信息
3. 调用 `add_rule.py` 写入新规则
4. 提醒你审核

## 3. 直接使用脚本管理规则

你也可以直接（或通过 Agent）使用脚本管理规则：

### 新增规则

```bash
python .agents/skills/self-evolve/scripts/add_rule.py \
  --title "标题" \
  --statement "规则描述" \
  --rationale "原因" \
  --domain debugging \
  --tag env
```

### 列出规则

```bash
python .agents/skills/self-evolve/scripts/list_rules.py
python .agents/skills/self-evolve/scripts/list_rules.py --domain debugging
python .agents/skills/self-evolve/scripts/list_rules.py --keyword "环境变量"
python .agents/skills/self-evolve/scripts/list_rules.py --detail
```

### 搜索规则（从 catalog.json）

```bash
python .agents/skills/self-evolve/scripts/find_rules.py --stats
python .agents/skills/self-evolve/scripts/find_rules.py --keyword "environment"
python .agents/skills/self-evolve/scripts/find_rules.py --detail --domain debugging
```

### 编辑规则

```bash
python .agents/skills/self-evolve/scripts/edit_rule.py R-001 --title "新标题"
python .agents/skills/self-evolve/scripts/edit_rule.py R-001 --statement "新描述" --rationale "新原因"
```

### 停用规则

```bash
python .agents/skills/self-evolve/scripts/retire_rule.py R-001
```

## 4. 同步到 Skill 输出

```bash
agent-kit self-evolve sync
```

同步会：
- 将所有 `active` 规则渲染到 `SKILL.md`
- 生成 `catalog.json` 供脚本检索
- 复制所有管理脚本到 Skill 输出目录

## 5. 通过 Git diff 审核

新规则写入后，使用 `git diff` 查看变更，确认后提交：

```bash
git diff .agents/self-evolve/rules/
git add .agents/
git commit -m "feat: add new knowledge rules"
```

## 6. 查看状态

```bash
agent-kit self-evolve status
```

输出当前规则数量和状态分布。

## 配置说明

配置文件：`.agents/self-evolve/config.jsonc`

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `language` | 模板语言 | `init` 时选择 |
| `inline_threshold` | inline/index 策略切换阈值 | `20` |

模板语言决议顺序：项目配置 `language` → `AGENT_KIT_LANG` → `en`
