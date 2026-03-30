# self-evolve

项目级自我进化插件，为 agent-kit 提供统一的知识管理能力。

## 核心特性

- **统一存储**：所有数据存储在项目根目录的 `.agent/` 目录中，不区分智能体类型
- **技能集成**：初始化后自动生成技能描述文件，智能体可以技能方式发现和使用
- **记忆管理**：支持捕获、查询规则（rule）、模式（pattern）和学习记录（learning）
- **CLI 命令**：用户可通过命令行手动管理记忆和技能

## 快速开始

```bash
# 安装插件
agent-kit plugins install self-evolve

# 在项目根目录初始化
agent-kit self-evolve init

# 捕获一条规则
agent-kit self-evolve capture --category rule --subject "命名规范" --content "使用 camelCase 命名变量"

# 列出所有记忆
agent-kit self-evolve list

# 按类别筛选
agent-kit self-evolve list --category rule

# 查看记忆详情
agent-kit self-evolve show m-001

# 查看状态
agent-kit self-evolve status

# 列出可用技能
agent-kit self-evolve skill list

# 查看技能详情
agent-kit self-evolve skill show self-evolve
```

## `.agent/` 目录结构

初始化后，项目根目录会生成以下结构：

```
.agent/
├── config.jsonc           # 项目级配置
├── memories/              # 记忆存储
│   ├── m-001.jsonc
│   └── m-002.jsonc
└── skills/                # 技能目录（智能体可发现）
    └── self-evolve/
        └── SKILL.md       # 自我进化技能描述
```

## 记忆类别

| 类别 | 说明 | 用途 |
|------|------|------|
| `rule` | 项目规则 | 必须遵守的约束和规范 |
| `pattern` | 代码模式 | 反复出现的代码结构和做法 |
| `learning` | 学习记录 | 从实践中获得的经验教训 |

## 技能集成

初始化后，`.agent/skills/self-evolve/SKILL.md` 会被自动生成。智能体可以通过发现该文件了解如何使用自我进化系统：

- 在任务开始前查阅已有规则和模式
- 在工作中发现值得记录的内容时自动捕获
- 通过技能描述了解可用命令和最佳实践

## 短命令别名

`se` 是 `self-evolve` 的短别名：

```bash
agent-kit se init
agent-kit se capture --category rule --subject "..." --content "..."
agent-kit se list
```
