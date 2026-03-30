# self-evolve 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `self-evolve` 自身的业务约束。

## 1. 插件目标

`self-evolve` 负责为 Agent 提供自我进化能力：通过结构化的学习捕获、模式识别、规则推广和技能提取，形成"经验 → 模式 → 规则 → 技能"的闭环演进系统。

## 2. 命令

当前插件对外提供以下命令：

- `agent-kit self-evolve wizard`
- `agent-kit self-evolve capture`
- `agent-kit self-evolve list`
- `agent-kit self-evolve analyze`
- `agent-kit self-evolve promote`
- `agent-kit self-evolve extract-skill`
- `agent-kit self-evolve status`

对应实现入口：

- [src/self_evolve/plugin_cli.py](src/self_evolve/plugin_cli.py)
- [src/self_evolve/messages.py](src/self_evolve/messages.py)
- [src/self_evolve/locale.py](src/self_evolve/locale.py)

## 3. 配置

配置文件位置：

- `~/.config/agent-kit/plugins/self-evolve/config.jsonc`

当前配置核心字段：

- `plugin_id`
- `config_version`
- `skills_target_dir`
- `promotion_threshold`
- `promotion_window_days`
- `min_task_count`

配置读写实现：

- [src/self_evolve/config.py](src/self_evolve/config.py)

## 4. 数据存储

学习条目存储位置：

- `~/.local/share/agent-kit/plugins/self-evolve/learnings/`

推广规则存储位置：

- `~/.local/share/agent-kit/plugins/self-evolve/rules.jsonc`

存储实现：

- [src/self_evolve/storage.py](src/self_evolve/storage.py)

## 5. 核心概念

- **学习条目**（Learning Entry）：结构化的经验记录，包含摘要、领域、优先级、模式键等字段。
- **模式识别**（Pattern Detection）：通过 `pattern_key` 精确匹配，自动关联相似条目并递增重复计数。
- **推广**（Promotion）：当学习满足门槛条件（重复次数 ≥ 阈值、跨任务出现、时间窗口内），可提炼为永久规则。
- **技能提取**（Skill Extraction）：将学习转化为符合 Agent Skills 规范的 `SKILL.md` 文件，安装到目标目录。

## 6. 业务规则

- 学习条目按单文件存储，文件名为 `<learning-id>.jsonc`。
- 学习 ID 格式为 `L-YYYYMMDD-NNN`，自动递增。
- 推广规则 ID 格式为 `R-NNN`，自动递增。
- 模式识别采用 `pattern_key` 精确匹配，不做模糊语义匹配。
- 推广条件三项须同时满足：`recurrence_count >= threshold`、`len(task_ids) >= min_task_count`、时间窗口内。
- 技能提取生成标准 `SKILL.md`（YAML frontmatter + Markdown 正文）。
- 提取后学习条目状态更新为 `promoted_to_skill`。

## 7. 修改本插件时重点验证

- `wizard` 是否正确初始化配置
- `capture` 是否正确生成唯一 ID 并存储条目
- `list` 是否正确按状态/领域/优先级过滤
- `analyze` 是否正确识别模式、关联条目、递增计数
- `promote` 是否正确检查推广条件并生成规则
- `extract-skill` 是否正确生成 SKILL.md
- `status` 是否正确统计各维度数据
- 中英文下的 `--help`、warning/error、状态输出是否保持一致

相关测试：

- [tests/test_self_evolve_cli.py](tests/test_self_evolve_cli.py)
- [tests/test_self_evolve_logic.py](tests/test_self_evolve_logic.py)
