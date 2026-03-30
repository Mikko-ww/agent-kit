# self-evolve 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `self-evolve` 自身的业务约束。

## 1. 插件目标

`self-evolve` 负责在项目根目录的 `.agent/` 目录中统一管理自我进化数据，包括记忆（规则、模式、学习记录）和技能描述，不区分智能体类型，适配所有智能体。

## 2. 命令

当前插件对外提供以下命令：

- `agent-kit self-evolve init`
- `agent-kit self-evolve capture`
- `agent-kit self-evolve list`
- `agent-kit self-evolve show`
- `agent-kit self-evolve status`
- `agent-kit self-evolve skill list`
- `agent-kit self-evolve skill show`

core 侧当前还提供固定短名 alias：

- `agent-kit se ...` 等价于 `agent-kit self-evolve ...`

对应实现入口：

- [src/self_evolve/plugin_cli.py](src/self_evolve/plugin_cli.py)
- [src/self_evolve/messages.py](src/self_evolve/messages.py)
- [src/self_evolve/locale.py](src/self_evolve/locale.py)

## 3. 配置

### 全局插件配置

位置：`~/.config/agent-kit/plugins/self-evolve/config.jsonc`

字段：
- `plugin_id`
- `config_version`
- `project_root`

### 项目级配置

位置：`<project_root>/.agent/config.jsonc`

字段：
- `plugin_id`
- `config_version`

配置读写实现：[src/self_evolve/config.py](src/self_evolve/config.py)

## 4. 数据存储

所有数据统一存储在项目根目录的 `.agent/` 目录中：

```
.agent/
├── config.jsonc           # 项目级配置
├── memories/              # 记忆存储（JSONC 格式）
│   ├── m-001.jsonc
│   └── m-002.jsonc
└── skills/                # 技能目录
    └── self-evolve/
        └── SKILL.md       # 自我进化技能描述
```

## 5. 业务规则

- 初始化时自动生成 `.agent/skills/self-evolve/SKILL.md` 技能描述文件。
- 记忆分三类：`rule`（规则）、`pattern`（模式）、`learning`（学习记录）。
- 记忆 ID 从 `m-001` 开始自增。
- 技能发现扫描 `.agent/skills/` 下所有包含 `SKILL.md` 的子目录。
- 用户可在 `.agent/skills/` 下手动添加自定义技能。
- 不区分智能体类型，所有数据对所有智能体通用。
- 当前仅支持 macOS / Linux。

核心业务实现：[src/self_evolve/logic.py](src/self_evolve/logic.py)

## 6. 修改本插件时重点验证

- `init` 是否正确创建 `.agent/` 目录结构和技能描述文件
- `capture` 是否正确写入记忆文件并自增 ID
- `list` 是否支持全部列出和按类别筛选
- `show` 是否正确展示记忆详情
- `status` 是否正确统计各类别数量
- `skill list` 是否发现所有技能（含自定义技能）
- `skill show` 是否正确展示技能信息
- 中英文下的 `--help`、提示和错误信息是否保持一致

相关测试：

- [tests/test_self_evolve_cli.py](tests/test_self_evolve_cli.py)
- [tests/test_self_evolve_logic.py](tests/test_self_evolve_logic.py)
