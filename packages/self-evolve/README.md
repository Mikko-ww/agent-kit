# self-evolve

`self-evolve` 是 `agent-kit` 的第一方插件，用来把项目内的结构化工作会话沉淀成可审核、可追溯、可同步的知识规则。

它不再使用旧版的 `learning -> analyze -> promote -> evolve` 模型，而是固定采用下面这条流水线：

```text
session -> candidate -> rule -> skill sync
```

## 核心模型

- `session`：一次任务或开发会话的结构化事实输入。
- `candidate`：从 session 中检测出的待确认知识候选。
- `rule`：已经批准、可直接供 Agent 消费的正式规则。
- `skill sync`：把 active rule 同步到 `.agents/skills/self-evolve/`。

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

初始化后会创建：

- `.agents/self-evolve/config.jsonc`
- `.agents/self-evolve/sessions/`
- `.agents/self-evolve/candidates/`
- `.agents/self-evolve/rules/`
- `.agents/self-evolve/indexes/`
- `.agents/skills/self-evolve/SKILL.md`

### 2. 记录 session

```bash
agent-kit self-evolve session record \
  --summary "修复启动阶段环境变量校验" \
  --domain debugging \
  --outcome success \
  --lesson "服务启动前必须先校验必填环境变量" \
  --tag env \
  --file src/app.py
```

### 3. 运行候选检测

```bash
agent-kit self-evolve detect run
```

### 4. 审核 candidate

```bash
agent-kit self-evolve candidate list
agent-kit self-evolve candidate show C-001
agent-kit self-evolve candidate accept C-001
```

### 5. 或直接录入正式 rule

```bash
agent-kit self-evolve rule add \
  --title "启动前校验环境变量" \
  --statement "在服务启动前校验所有必填环境变量。" \
  --rationale "避免进入部分启动成功、运行时再失败的状态。" \
  --domain debugging \
  --tag env
```

### 6. 同步 Skill

```bash
agent-kit self-evolve sync
```

## 命令总览

### 根命令

- `agent-kit self-evolve init`
- `agent-kit self-evolve sync`
- `agent-kit self-evolve status`

### session

- `agent-kit self-evolve session record`

### detect

- `agent-kit self-evolve detect run`

### candidate

- `agent-kit self-evolve candidate list`
- `agent-kit self-evolve candidate show <candidate-id>`
- `agent-kit self-evolve candidate accept <candidate-id>`
- `agent-kit self-evolve candidate reject <candidate-id>`
- `agent-kit self-evolve candidate edit <candidate-id>`

### rule

- `agent-kit self-evolve rule add`
- `agent-kit self-evolve rule list`
- `agent-kit self-evolve rule show <rule-id>`
- `agent-kit self-evolve rule edit <rule-id>`
- `agent-kit self-evolve rule retire <rule-id>`

## 配置

配置文件位置：

- `<project-root>/.agents/self-evolve/config.jsonc`

当前字段：

```jsonc
{
  "plugin_id": "self-evolve",
  "config_version": 4,
  "auto_accept_enabled": false,
  "auto_accept_min_confidence": 0.9,
  "inline_threshold": 20
}
```

- `auto_accept_enabled`：是否允许候选在检测阶段自动生效。
- `auto_accept_min_confidence`：自动生效所需最低置信度。
- `inline_threshold`：Skill 输出在 inline/index 策略之间切换的阈值。

## 数据布局

```text
<project-root>/
├── .agents/
│   ├── self-evolve/
│   │   ├── config.jsonc
│   │   ├── sessions/
│   │   ├── candidates/
│   │   ├── rules/
│   │   └── indexes/
│   └── skills/
│       └── self-evolve/
│           ├── SKILL.md
│           ├── catalog.json
│           ├── scripts/find_rules.py
│           └── domains/
```

## Skill 输出

`sync` 只消费 `status=active` 的正式 rule，不会把 candidate 或 session 暴露给 Skill 消费侧。

- `inline`：规则数不超过 `inline_threshold` 时，直接内联到 `SKILL.md`
- `index`：规则数超阈值时，`SKILL.md` 只给索引，详细内容写入 `domains/*.md`

项目内可直接用脚本检索：

```bash
python .agents/skills/self-evolve/scripts/find_rules.py --stats
python .agents/skills/self-evolve/scripts/find_rules.py --keyword "environment"
python .agents/skills/self-evolve/scripts/find_rules.py --detail --domain debugging
```

## 重要说明

- 不做任何前向兼容。
- 旧版 `.agents/self-evolve/learnings/`、`.agents/self-evolve/rules.jsonc` 和旧 CLI 已全部废弃。
- 发现旧布局时会直接报错，不提供自动迁移。
- CLI 继续支持 `en` 与 `zh-CN`，语言决议顺序与 `agent-kit` core 保持一致。
