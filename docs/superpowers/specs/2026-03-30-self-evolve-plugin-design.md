# self-evolve 自我进化 Agent Skill 插件设计

## 摘要

`self-evolve` 是 `agent-kit` 的第一方插件，核心目的是让 Agent 能够从工作经验中持续学习和进化。插件通过结构化的学习捕获、模式识别、规则推广和技能提取，形成一个"经验 → 模式 → 规则 → 技能"的闭环演进系统。

## 目标

- 提供结构化的学习日志系统，捕获 Agent 在任务执行过程中的关键发现
- 通过模式识别和重复检测，自动发现高频问题和可复用知识
- 将经过验证的学习推广为永久规则，沉淀到项目配置中
- 将具备跨项目复用价值的学习提取为独立 Skill，安装到指定目录
- 提供可视化的进化状态概览，量化学习进度

## 非目标

- 不实现跨网络的多 Agent 实时协作（v1 仅支持本地文件共享）
- 不实现自动 Hook 触发机制（v1 仅支持手动触发）
- 不实现 LLM 驱动的自动学习捕获
- 不替代 core 的记忆系统或现有 skills-link 功能

## 插件基础信息

| 字段 | 值 |
|------|-----|
| `plugin_id` | `self-evolve` |
| `display_name` | `Self Evolve` |
| `分发包名` | `self-evolve` |
| `Python 模块名` | `self_evolve` |
| `目录` | `packages/self-evolve` |
| `API_VERSION` | `1` |
| `CONFIG_VERSION` | `1` |
| `初始版本` | `0.1.0` |

## 核心概念

### 1. 学习条目（Learning Entry）

每条学习记录包含以下结构化字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 唯一 ID，格式 `L-YYYYMMDD-NNN` |
| `timestamp` | `str` | ISO 8601 时间戳 |
| `priority` | `str` | 优先级：`low`、`medium`、`high`、`critical` |
| `status` | `str` | 状态：`active`、`resolved`、`promoted`、`promoted_to_skill` |
| `domain` | `str` | 领域标签，如 `debugging`、`testing`、`architecture` |
| `summary` | `str` | 简要摘要 |
| `detail` | `str` | 详细描述 |
| `suggested_action` | `str` | 建议操作 |
| `pattern_key` | `str` | 模式键，用于关联相似条目 |
| `see_also` | `list[str]` | 关联条目 ID 列表 |
| `recurrence_count` | `int` | 重复出现次数 |
| `task_ids` | `list[str]` | 出现过的任务 ID 列表 |
| `metadata` | `dict` | 可选扩展元数据 |

### 2. 推广规则（Promotion Rule）

当学习条目满足推广条件时，提炼为简洁规则存入规则库：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 规则 ID，格式 `R-NNN` |
| `source_learning_id` | `str` | 来源学习条目 ID |
| `rule` | `str` | 简洁规则描述 |
| `domain` | `str` | 适用领域 |
| `created_at` | `str` | 创建时间 |

推广条件：

- `recurrence_count >= promotion_threshold`（默认 3）
- 在至少 `min_task_count` 个不同任务中出现（默认 2）
- 在 `promotion_window_days` 天内发生（默认 30）

### 3. 技能提取（Skill Extraction）

当学习满足以下条件时，可提取为可复用 Skill：

- 有 2 个以上 `see_also` 链接
- 状态为 `resolved` 且解决方案已验证
- 需要实际调试才能发现（非显而易见）
- 跨代码库有用（非项目特定）

提取结果：

- 在配置的 `skills_target_dir` 下创建 `<skill-name>/SKILL.md`
- 遵循 Agent Skills 规范（YAML frontmatter + Markdown 正文）
- 更新原学习条目状态为 `promoted_to_skill`

## CLI 命令设计

### `agent-kit self-evolve wizard`

交互式配置向导，用于初始化或更新插件配置。

### `agent-kit self-evolve capture`

捕获一条新的学习记录。

选项：
- `--summary` / `-s`：简要摘要（必填）
- `--domain` / `-d`：领域标签（必填）
- `--priority` / `-p`：优先级（默认 `medium`）
- `--detail`：详细描述（可选）
- `--action`：建议操作（可选）
- `--pattern-key`：模式键（可选）
- `--task-id`：关联任务 ID（可选）

### `agent-kit self-evolve list`

列出学习记录。

选项：
- `--status`：按状态过滤
- `--domain`：按领域过滤
- `--priority`：按优先级过滤
- `--limit`：显示条数（默认 20）

### `agent-kit self-evolve analyze`

分析现有学习记录：

- 检测重复模式（相同 `pattern_key`）
- 自动关联相似条目（更新 `see_also`）
- 递增 `recurrence_count`
- 标记满足推广条件的候选条目

### `agent-kit self-evolve promote`

将一条学习推广为永久规则。

参数：
- `LEARNING_ID`：要推广的学习条目 ID

选项：
- `--rule`：规则描述（可选，未指定则交互式输入）

### `agent-kit self-evolve extract-skill`

将一条学习提取为可复用的 Skill。

参数：
- `LEARNING_ID`：要提取的学习条目 ID

选项：
- `--name`：Skill 名称（可选，未指定则交互式输入）

### `agent-kit self-evolve status`

显示整体进化状态概览：

- 总学习条目数
- 各状态分布
- 推广规则数
- 已提取技能数
- 近期活跃领域

## 配置设计

配置文件：`~/.config/agent-kit/plugins/self-evolve/config.jsonc`

```jsonc
{
  "plugin_id": "self-evolve",
  "config_version": 1,
  // 提取的 Skill 安装目标目录
  "skills_target_dir": "~/.agents/skills",
  // 推广门槛：重复出现次数
  "promotion_threshold": 3,
  // 推广时间窗口（天）
  "promotion_window_days": 30,
  // 推广最少任务数
  "min_task_count": 2
}
```

## 数据存储设计

所有持久化数据存储在 `data_root` 下：

```
~/.local/share/agent-kit/plugins/self-evolve/
├── learnings/
│   ├── L-20260330-001.jsonc
│   ├── L-20260330-002.jsonc
│   └── ...
└── rules.jsonc
```

- 学习条目按单文件存储，便于管理和浏览
- 规则集中存储在 `rules.jsonc`

## 与 core 的职责边界

| 职责 | 归属 |
|------|------|
| 插件安装/更新/卸载 | core |
| 语言决议与透传 | core |
| 学习捕获与存储 | self-evolve |
| 模式识别与分析 | self-evolve |
| 规则推广与管理 | self-evolve |
| 技能提取与安装 | self-evolve |
| Skill 文件链接到多目标 | skills-link（互补） |

## 测试范围

- 配置加载/保存/版本校验
- 学习条目 CRUD 操作
- 模式识别与重复检测逻辑
- 推广条件判断与规则生成
- 技能提取与 SKILL.md 生成
- CLI 命令中英文输出
- 交互式向导流程

## 风险与取舍

### 风险

- 学习条目增长过快，需要考虑归档或清理机制
- 模式识别依赖 `pattern_key` 的人工标注，自动化程度有限

### 取舍

- v1 不实现自动 Hook 触发，保持手动操作的可控性
- v1 不实现跨网络协作，仅通过文件系统共享
- 模式识别采用精确匹配 `pattern_key`，不做模糊语义匹配
