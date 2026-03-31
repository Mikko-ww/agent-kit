# self-evolve

`self-evolve` 是 `agent-kit` 的第一方插件，用来把项目中的可复用知识沉淀为结构化规则，并自动同步到 Agent 可消费的 Skill 输出。

v5 采用 Rule-only 极简架构：

```text
Agent 反思 → 脚本写入 Rule → sync → SKILL.md
```

## 核心模型

- `Rule`：已批准的正式规则，由 Agent 通过脚本直接创建和管理。
- `Skill sync`：把 active rule 同步到 `.agents/skills/self-evolve/`。

## 安装

```bash
agent-kit plugins install self-evolve
```

## 快速开始

### 1. 初始化项目

```bash
cd your-project
agent-kit self-evolve init
```

`init` 会在创建项目知识库时询问一次模板语言，只允许选择 `en` 或 `zh-CN`。

初始化后会创建：

- `.agents/self-evolve/config.jsonc`
- `.agents/self-evolve/rules/`
- `.agents/skills/self-evolve/SKILL.md`
- `.agents/skills/self-evolve/scripts/`

### 2. 通过 Skill 触发反思注入

当 Agent 加载了 `SKILL.md` 后，用户可以要求 Agent "总结本次经验" 或 "提取规则"。Agent 会按照 Skill 中的反思注入指令，自动调用脚本写入规则。

### 3. 直接使用脚本管理规则

```bash
# 新增规则
python .agents/skills/self-evolve/scripts/add_rule.py \
  --title "启动前校验环境变量" \
  --statement "在服务启动前校验所有必填环境变量。" \
  --rationale "避免进入部分启动成功、运行时再失败的状态。" \
  --domain debugging \
  --tag env

# 列出规则
python .agents/skills/self-evolve/scripts/list_rules.py

# 搜索规则
python .agents/skills/self-evolve/scripts/find_rules.py --keyword "environment"

# 编辑规则
python .agents/skills/self-evolve/scripts/edit_rule.py R-001 --title "新标题"

# 停用规则
python .agents/skills/self-evolve/scripts/retire_rule.py R-001
```

### 4. 同步到 Skill 输出

```bash
agent-kit self-evolve sync
```

### 5. 通过 Git diff 审核

新规则写入后，建议通过 `git diff` 审核后再提交。

## 命令总览

- `agent-kit self-evolve init`
- `agent-kit self-evolve sync`
- `agent-kit self-evolve status`

## 配置

配置文件位置：

- `<project-root>/.agents/self-evolve/config.jsonc`

当前字段：

```jsonc
{
  "plugin_id": "self-evolve",
  "config_version": 5,
  "language": "zh-CN",
  "inline_threshold": 20
}
```

- `language`：项目模板语言。`init` 时由用户选择并写入配置；后续 `sync` 优先使用该值。
- `inline_threshold`：Skill 输出在 inline/index 策略之间切换的阈值。

模板语言决议固定为：

1. 项目配置中的 `language`
2. `AGENT_KIT_LANG`
3. `en`

## 数据布局

```text
<project-root>/
├── .agents/
│   ├── self-evolve/
│   │   ├── config.jsonc
│   │   └── rules/
│   └── skills/
│       └── self-evolve/
│           ├── SKILL.md
│           ├── catalog.json
│           ├── scripts/
│           │   ├── add_rule.py
│           │   ├── edit_rule.py
│           │   ├── retire_rule.py
│           │   ├── list_rules.py
│           │   └── find_rules.py
│           └── domains/
```

## Skill 输出

`sync` 只消费 `status=active` 的正式 rule。

- `inline`：规则数不超过 `inline_threshold` 时，直接内联到 `SKILL.md`
- `index`：规则数超阈值时，`SKILL.md` 只给索引，详细内容写入 `domains/*.md`

SKILL.md 包含反思注入指令，引导 Agent 从对话上下文中提取结构化知识并调用脚本写入规则。

## 重要说明

- v5 是完全重写，不兼容旧版本。
- CLI 继续支持 `en` 与 `zh-CN`，语言决议顺序与 `agent-kit` core 保持一致。
- Skill 模板语言与 CLI 语言解耦：CLI 继续跟随 core 决议链，生成模板则优先遵循项目配置中的 `language`。
