# self-evolve 使用指南

`self-evolve` 是 `agent-kit` 的第一方插件，为项目提供一条 **结构化知识流水线**，帮助团队（包括人类与 AI Agent）把开发过程中的经验和教训沉淀为可审核、可追溯、可同步的正式规则，并以 Skill 形式供所有 Agent 自动消费。

## 目录

- [核心概念](#核心概念)
- [安装](#安装)
- [快速上手](#快速上手)
- [完整工作流详解](#完整工作流详解)
  - [1. 初始化项目](#1-初始化项目)
  - [2. 记录 Session](#2-记录-session)
  - [3. 运行候选检测](#3-运行候选检测)
  - [4. 审核 Candidate](#4-审核-candidate)
  - [5. 直接录入 Rule](#5-直接录入-rule)
  - [6. 同步 Skill](#6-同步-skill)
  - [7. 查看状态](#7-查看状态)
- [命令参考](#命令参考)
  - [根命令](#根命令)
  - [session 子命令](#session-子命令)
  - [detect 子命令](#detect-子命令)
  - [candidate 子命令](#candidate-子命令)
  - [rule 子命令](#rule-子命令)
- [配置说明](#配置说明)
- [数据与目录布局](#数据与目录布局)
- [Skill 输出与消费](#skill-输出与消费)
  - [输出策略](#输出策略)
  - [使用 find_rules.py 检索规则](#使用-find_rulespy-检索规则)
- [候选检测器机制](#候选检测器机制)
  - [候选生成规则](#候选生成规则)
  - [置信度评分](#置信度评分)
  - [自动生效](#自动生效)
- [实际使用场景示例](#实际使用场景示例)
  - [场景一：调试后沉淀经验](#场景一调试后沉淀经验)
  - [场景二：直接录入已知规则](#场景二直接录入已知规则)
  - [场景三：Agent 自动记录](#场景三agent-自动记录)
- [语言设置](#语言设置)
- [旧版迁移说明](#旧版迁移说明)
- [常见问题](#常见问题)

---

## 核心概念

`self-evolve` 围绕四个核心实体构成一条固定流水线：

```text
Session → Candidate → Rule → Skill Sync
```

| 实体 | 说明 |
|------|------|
| **Session** | 一次任务或开发会话的结构化事实记录，是流水线的唯一主输入 |
| **Candidate** | 由检测器从 Session 中提炼出的待确认知识候选 |
| **Rule** | 经过人工审核或自动生效后批准的正式规则 |
| **Skill Sync** | 将所有 `active` 状态的 Rule 同步到 `.agents/skills/self-evolve/`，供 Agent 直接消费 |

### 实体状态

- **Session**：`processed=false`（待处理） → `processed=true`（已处理）
- **Candidate**：`open` → `accepted` / `rejected` / `auto_accepted` / `superseded`
- **Rule**：`active`（生效中） → `retired`（已停用）

---

## 安装

```bash
agent-kit plugins install self-evolve
```

安装后可通过 `agent-kit self-evolve --help` 查看可用命令。

---

## 快速上手

以下是一次从零到有的最小操作路径：

```bash
# 1. 在项目根目录初始化
cd your-project
agent-kit self-evolve init

# 2. 记录一条 session
agent-kit self-evolve session record \
  --summary "修复启动阶段环境变量校验" \
  --domain debugging \
  --outcome success \
  --lesson "服务启动前必须先校验必填环境变量"

# 3. 运行检测，从 session 生成 candidate
agent-kit self-evolve detect run

# 4. 查看并接受 candidate
agent-kit self-evolve candidate list
agent-kit self-evolve candidate accept C-001

# 5. 同步到 Skill 输出
agent-kit self-evolve sync
```

完成后，`.agents/skills/self-evolve/SKILL.md` 就会包含已批准的规则，任何读取 Skill 的 Agent 都能自动遵循这些规则。

---

## 完整工作流详解

### 1. 初始化项目

```bash
agent-kit self-evolve init
```

`init` 会在交互式终端中要求你选择模板语言（仅支持 `en` 或 `zh-CN`），默认值来自环境变量 `AGENT_KIT_LANG`。所选语言会写入配置文件，后续 `sync` 和模板生成时持续使用。

初始化完成后会创建以下目录结构：

```text
<project-root>/
├── .agents/
│   ├── self-evolve/
│   │   ├── config.jsonc      # 插件配置
│   │   ├── sessions/         # session 存储
│   │   ├── candidates/       # candidate 存储
│   │   ├── rules/            # rule 存储
│   │   └── indexes/          # 追溯索引
│   └── skills/
│       └── self-evolve/
│           └── SKILL.md       # 初始 Skill（空规则集）
```

> 如果已初始化，再次运行 `init` 会提示"项目已初始化"，不会覆盖已有数据。

### 2. 记录 Session

Session 是流水线的唯一输入源，记录一次任务中的关键事实。

```bash
agent-kit self-evolve session record \
  --summary "修复启动校验" \
  --domain debugging \
  --outcome success \
  --source agent \
  --observation "服务启动时没有校验环境变量" \
  --observation "缺少变量时进入了半启动状态" \
  --decision "在 main 函数入口增加 check_env() 调用" \
  --fix "添加 check_env() 校验所有必填变量" \
  --lesson "服务启动前必须先校验必填环境变量" \
  --file src/app.py \
  --tag env \
  --tag startup
```

#### Session 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--summary` | 是 | 本次 session 的简要描述 |
| `--domain` | 是 | 知识所属领域（如 `debugging`、`testing`、`architecture`） |
| `--outcome` | 是 | 结果：`success`、`failure` 或 `partial` |
| `--source` | 否 | 来源，默认 `agent`；也可以是 `human` 等自定义值 |
| `--observation` | 否 | 观察到的事实，可多次使用 |
| `--decision` | 否 | 做出的决定，可多次使用 |
| `--fix` | 否 | 实施的修复，可多次使用 |
| `--lesson` | 否 | 总结的教训/经验，可多次使用 |
| `--file` | 否 | 涉及的文件路径，可多次使用 |
| `--tag` | 否 | 标签，可多次使用 |

Session 记录后会生成一个唯一 ID（格式：`S-YYYYMMDD-NNN`），并保存为独立 JSON 文件。

> **提示**：`--lesson` 是候选检测的最优质输入。如果你已经能总结出经验，请尽量通过 `--lesson` 提供。

### 3. 运行候选检测

```bash
# 处理所有未处理的 session
agent-kit self-evolve detect run

# 或指定处理特定 session
agent-kit self-evolve detect run --session-id S-20260331-001
```

检测器会扫描未处理的 Session，根据 `lessons`、`observations`、`fixes` 等字段生成 Candidate。详见 [候选检测器机制](#候选检测器机制) 章节。

### 4. 审核 Candidate

```bash
# 列出所有 candidate（默认最多 20 条）
agent-kit self-evolve candidate list

# 按状态/领域/标签/关键词过滤
agent-kit self-evolve candidate list --status open
agent-kit self-evolve candidate list --domain debugging
agent-kit self-evolve candidate list --tag env
agent-kit self-evolve candidate list --keyword "环境变量"

# 查看单个 candidate 详情
agent-kit self-evolve candidate show C-001

# 接受 candidate → 自动创建对应 rule
agent-kit self-evolve candidate accept C-001

# 拒绝 candidate
agent-kit self-evolve candidate reject C-002

# 编辑 candidate（修改后再决定是否接受）
agent-kit self-evolve candidate edit C-003 \
  --title "优化后的标题" \
  --statement "更精确的规则描述"
```

接受 Candidate 时，会自动：
1. 创建一条 `active` 状态的 Rule
2. 将 Candidate 状态标记为 `accepted`
3. 将同 fingerprint 的其他 `open` Candidate 标记为 `superseded`
4. 刷新索引

### 5. 直接录入 Rule

如果你已经明确知道要沉淀的规则，可以跳过 Session → Candidate 流程，直接录入：

```bash
agent-kit self-evolve rule add \
  --title "启动前校验环境变量" \
  --statement "在服务启动前校验所有必填环境变量。" \
  --rationale "避免进入部分启动成功、运行时再失败的状态。" \
  --domain debugging \
  --tag env \
  --tag startup
```

#### Rule 管理

```bash
# 列出所有 rule
agent-kit self-evolve rule list

# 按条件过滤
agent-kit self-evolve rule list --status active
agent-kit self-evolve rule list --domain debugging
agent-kit self-evolve rule list --keyword "环境变量"

# 查看详情
agent-kit self-evolve rule show R-001

# 编辑 rule
agent-kit self-evolve rule edit R-001 \
  --title "更新后的标题" \
  --statement "更新后的规则描述"

# 停用 rule（不再出现在 Skill 输出中）
agent-kit self-evolve rule retire R-001
```

### 6. 同步 Skill

```bash
agent-kit self-evolve sync
```

`sync` 会读取所有 `status=active` 的 Rule，生成以下文件：

- `.agents/skills/self-evolve/SKILL.md` — Agent 可读取的 Skill 文档
- `.agents/skills/self-evolve/catalog.json` — 结构化规则目录（v2 格式）
- `.agents/skills/self-evolve/scripts/find_rules.py` — 规则检索脚本
- `.agents/skills/self-evolve/domains/*.md` — 仅在 `index` 策略下生成的领域详情页

> **重要**：每次接受 Candidate 或修改 Rule 后，都需要运行 `sync` 才能让变更反映到 Skill 输出中。

### 7. 查看状态

```bash
agent-kit self-evolve status
```

输出示例：

```text
会话：总数=5，已处理=3，待处理=2
候选：open=2, accepted=1, rejected=1
规则：active=2, retired=1
```

---

## 命令参考

### 根命令

| 命令 | 说明 |
|------|------|
| `agent-kit self-evolve init` | 初始化项目，创建数据目录与配置文件 |
| `agent-kit self-evolve sync` | 将 active Rule 同步到 Skill 输出 |
| `agent-kit self-evolve status` | 显示流水线当前状态概要 |

### session 子命令

| 命令 | 说明 |
|------|------|
| `agent-kit self-evolve session record` | 记录一条结构化 Session |

### detect 子命令

| 命令 | 说明 |
|------|------|
| `agent-kit self-evolve detect run` | 对未处理 Session 运行候选检测 |

`detect run` 支持 `--session-id` 参数，可指定处理特定 Session（可多次使用）。不指定时，默认只处理 `processed=false` 的 Session。

### candidate 子命令

| 命令 | 说明 |
|------|------|
| `agent-kit self-evolve candidate list` | 列出 Candidate |
| `agent-kit self-evolve candidate show <id>` | 查看单个 Candidate 详情 |
| `agent-kit self-evolve candidate accept <id>` | 接受 Candidate 并自动生成 Rule |
| `agent-kit self-evolve candidate reject <id>` | 拒绝 Candidate |
| `agent-kit self-evolve candidate edit <id>` | 编辑 Candidate 字段 |

**`list` 过滤参数**：`--status`、`--domain`、`--tag`、`--keyword`、`--limit`（默认 20）

**`edit` 可修改字段**：`--title`、`--statement`、`--rationale`、`--domain`、`--tag`

### rule 子命令

| 命令 | 说明 |
|------|------|
| `agent-kit self-evolve rule add` | 直接新增正式 Rule |
| `agent-kit self-evolve rule list` | 列出 Rule |
| `agent-kit self-evolve rule show <id>` | 查看单个 Rule 详情 |
| `agent-kit self-evolve rule edit <id>` | 编辑 Rule 字段 |
| `agent-kit self-evolve rule retire <id>` | 停用 Rule |

**`add` 必填参数**：`--title`、`--statement`、`--rationale`、`--domain`

**`add` 可选参数**：`--tag`、`--source-session-id`、`--source-candidate-id`

**`edit` 可修改字段**：`--title`、`--statement`、`--rationale`、`--domain`、`--tag`、`--revision-of`

---

## 配置说明

配置文件位于 `<project-root>/.agents/self-evolve/config.jsonc`，在 `init` 时自动创建。

```jsonc
{
  "plugin_id": "self-evolve",
  "config_version": 4,
  "language": "zh-CN",
  "auto_accept_enabled": false,
  "auto_accept_min_confidence": 0.9,
  "inline_threshold": 20
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `language` | `string` | `init` 时选择 | 模板语言，决定 Skill 输出的文档语言（`en` 或 `zh-CN`） |
| `auto_accept_enabled` | `bool` | `false` | 是否允许高置信度 Candidate 在 `detect run` 时自动生效 |
| `auto_accept_min_confidence` | `float` | `0.9` | 自动生效的最低置信度阈值 |
| `inline_threshold` | `int` | `20` | Skill 输出在 `inline` 和 `index` 策略之间切换的规则数阈值 |

可直接编辑此文件来调整配置。

---

## 数据与目录布局

```text
<project-root>/
├── .agents/
│   ├── self-evolve/
│   │   ├── config.jsonc                    # 插件配置
│   │   ├── sessions/
│   │   │   ├── S-20260331-001.json         # 独立 session 文件
│   │   │   └── S-20260331-002.json
│   │   ├── candidates/
│   │   │   ├── C-001.json                  # 独立 candidate 文件
│   │   │   └── C-002.json
│   │   ├── rules/
│   │   │   ├── R-001.json                  # 独立 rule 文件
│   │   │   └── R-002.json
│   │   └── indexes/
│   │       └── knowledge.json              # 追溯索引
│   └── skills/
│       └── self-evolve/
│           ├── SKILL.md                     # Skill 主文件（Agent 读取入口）
│           ├── catalog.json                 # 结构化规则目录
│           ├── scripts/
│           │   └── find_rules.py            # 规则检索脚本
│           └── domains/                     # index 策略时的领域详情
│               ├── debugging.md
│               └── testing.md
```

- 所有实体（Session、Candidate、Rule）均按单文件 JSON 存储，便于 Git 追踪和代码审查
- `indexes/knowledge.json` 维护 fingerprint、session、candidate、rule 之间的追溯关系
- `.agents/skills/self-evolve/` 是 `sync` 命令的输出目录，应当提交到版本控制中，以便其他开发者和 Agent 直接使用

---

## Skill 输出与消费

### 输出策略

`sync` 根据 active Rule 的数量自动选择策略：

| 策略 | 条件 | 行为 |
|------|------|------|
| **inline** | 规则数 ≤ `inline_threshold`（默认 20） | 所有规则内联到 `SKILL.md` 中 |
| **index** | 规则数 > `inline_threshold` | `SKILL.md` 仅显示索引表；详细内容写入 `domains/<domain>.md` |

`SKILL.md` 是 Agent 自动读取的入口文件。支持 Cursor、Copilot、Codex 等主流编码 Agent 的 Skill 发现机制。

### 使用 find_rules.py 检索规则

`sync` 会自动将检索脚本复制到 `.agents/skills/self-evolve/scripts/find_rules.py`，可用于在命令行中快速检索规则：

```bash
# 显示规则统计
python .agents/skills/self-evolve/scripts/find_rules.py --stats

# 按关键词搜索
python .agents/skills/self-evolve/scripts/find_rules.py --keyword "环境变量"

# 按领域过滤
python .agents/skills/self-evolve/scripts/find_rules.py --domain debugging

# 按标签过滤
python .agents/skills/self-evolve/scripts/find_rules.py --tag env

# 显示详细信息
python .agents/skills/self-evolve/scripts/find_rules.py --detail --domain debugging
```

---

## 候选检测器机制

当前版本的检测器只消费显式的 Session 输入，不扫描工作区文件，也不接入 LLM。

### 候选生成规则

检测器按以下优先级从 Session 生成 Candidate：

1. **优先从 `lessons[]` 生成**：每条 lesson 生成一个独立 Candidate
2. **若 `lessons[]` 为空**：按 `observations[]` 与 `fixes[]` 配对生成 Candidate（一一对应）

每个 Candidate 会生成一个 **fingerprint**（`domain:normalized-statement`），用于去重和追溯。如果已存在同 fingerprint 的 `open` Candidate，则合并（更新 source session、提高置信度），而不是创建新记录。

### 置信度评分

| 条件 | 分值 |
|------|------|
| 来自显式 `lesson` | 基础分 0.70 |
| 来自 `observation + fix` 配对 | 基础分 0.45 |
| Session `outcome=success` | +0.10 |
| 同 fingerprint 已在其他 Session 出现过 | +0.15 |
| 同 fingerprint 已有 `open` Candidate | +0.05 |
| 上限 | 1.0 |

### 自动生效

默认关闭。开启后，`detect run` 阶段满足以下全部条件的 Candidate 会自动转为 Rule：

1. 配置中 `auto_accept_enabled = true`
2. Candidate 的 `confidence >= auto_accept_min_confidence`（默认 0.9）
3. 该 fingerprint 当前没有 `active` 状态的 Rule

---

## 实际使用场景示例

### 场景一：调试后沉淀经验

你刚修复了一个 API 超时的问题，希望把这次调试经验留存下来：

```bash
# 记录 session
agent-kit self-evolve session record \
  --summary "修复 API 接口超时导致前端白屏" \
  --domain debugging \
  --outcome success \
  --observation "前端页面在网络差时白屏" \
  --observation "后端 /api/data 接口没有设置超时" \
  --fix "为所有外部 HTTP 调用设置 30s 超时" \
  --fix "前端增加超时重试和错误兜底" \
  --lesson "所有外部 HTTP 调用必须显式设置超时时间" \
  --file src/api/client.py \
  --file src/frontend/App.tsx \
  --tag api \
  --tag timeout

# 运行检测
agent-kit self-evolve detect run

# 查看并接受
agent-kit self-evolve candidate list
agent-kit self-evolve candidate accept C-001

# 同步到 Skill
agent-kit self-evolve sync
```

### 场景二：直接录入已知规则

团队已经达成共识的编码规范，无需走 Session → Candidate 流程：

```bash
agent-kit self-evolve rule add \
  --title "禁止在循环中发起数据库查询" \
  --statement "不得在 for/while 循环体内直接调用数据库查询，应改用批量查询或预加载。" \
  --rationale "避免 N+1 查询导致性能瓶颈。" \
  --domain performance \
  --tag database \
  --tag performance

agent-kit self-evolve sync
```

### 场景三：Agent 自动记录

在 Agent 的 Skill 或 workflow 中，可以让 Agent 在完成任务后自动调用 `session record`：

```bash
agent-kit self-evolve session record \
  --summary "重构用户认证模块" \
  --domain architecture \
  --outcome success \
  --source agent \
  --lesson "认证逻辑应集中在中间件层，不要分散到各个路由" \
  --lesson "JWT token 刷新逻辑需要独立函数，方便测试" \
  --tag auth \
  --tag refactor
```

然后由人工定期运行检测和审核：

```bash
agent-kit self-evolve detect run
agent-kit self-evolve candidate list --status open
# 逐个审核...
agent-kit self-evolve sync
```

---

## 语言设置

`self-evolve` 有两条独立的语言链路：

### CLI 提示语言

CLI 的命令帮助、提示信息、错误输出等语言，跟随 `agent-kit` core 的语言决议链：

```text
AGENT_KIT_LANG 环境变量 → ~/.config/agent-kit/config.jsonc 全局配置 → 系统语言环境 → en
```

### 模板语言

Skill 输出文件（`SKILL.md`、领域详情页等）的语言，使用独立的决议链：

```text
项目配置 .agents/self-evolve/config.jsonc 的 language → AGENT_KIT_LANG → en
```

两条链路互不干扰。例如，你可以在中文 shell 环境下工作，但让 Skill 输出使用英文。

---

## 旧版迁移说明

`self-evolve` v4 **不保留任何旧版兼容**。以下旧格式已全部废弃：

- `.agents/self-evolve/learnings/` 目录
- `.agents/self-evolve/rules.jsonc` 聚合文件
- 旧命令：`capture`、`analyze`、`promote`、`evolve`、`search`

如果检测到旧数据布局，插件会 **直接报错并终止**，不会自动迁移也不会读取旧数据。

如需继续使用，请手动清理旧数据目录后重新 `init`。

---

## 常见问题

### 项目已有 `.agents/self-evolve/` 目录，`init` 会覆盖吗？

不会。如果检测到已初始化过，`init` 会提示"项目已初始化"并退出，不会覆盖已有数据。

### Session 记录后可以修改吗？

Session 设计为不可原地改写的事实记录。如需修正，建议用新的 Session 重新记录正确内容。

### 接受 Candidate 后忘了 `sync` 会怎样？

Rule 已经创建成功，但 Skill 输出不会自动更新。Agent 读取的 `SKILL.md` 仍然是上次 `sync` 的结果。请手动运行 `agent-kit self-evolve sync` 来刷新。

### 如何停用一条已经生效的规则？

```bash
agent-kit self-evolve rule retire R-001
agent-kit self-evolve sync
```

`retire` 后该规则不会再出现在 Skill 输出中。

### `detect run` 会重复处理已处理的 Session 吗？

不会。默认只处理 `processed=false` 的 Session。如果你想重新处理某个 Session，可以使用 `--session-id` 参数显式指定。

### Candidate 的 fingerprint 是什么？

fingerprint 是一个由 `domain` 和 `statement` 归一化后拼接的去重键（格式：`domain:normalized-statement`），用于识别语义相同的 Candidate 和 Rule，避免重复。

### `.agents/` 下的文件应该提交到 Git 吗？

建议提交。这样团队所有成员和 Agent 都能共享相同的规则集。特别是 `.agents/skills/self-evolve/` 目录，它是 Agent 消费知识的入口。
