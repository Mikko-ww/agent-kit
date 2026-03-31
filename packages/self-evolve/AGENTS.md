# self-evolve 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `self-evolve` 自身的业务约束。

## 1. 插件目标

`self-evolve` 负责为 Agent 提供以项目为基础的自我进化能力：通过结构化的学习捕获、模式识别、规则推广和统一 Skill 同步，以 Skill 方式接入 Cursor、VS Code Copilot、Codex 等主流编码 Agent，形成"经验 → 模式 → 规则 → Agent Skill"的闭环演进系统。

## 2. 命令

当前插件对外提供以下命令：

- `agent-kit self-evolve init`
- `agent-kit self-evolve capture`
- `agent-kit self-evolve list`
- `agent-kit self-evolve analyze`
- `agent-kit self-evolve promote`
- `agent-kit self-evolve sync`
- `agent-kit self-evolve evolve`
- `agent-kit self-evolve status`
- `agent-kit self-evolve search`

对应实现入口：

- [src/self_evolve/plugin_cli.py](src/self_evolve/plugin_cli.py)
- [src/self_evolve/messages.py](src/self_evolve/messages.py)
- [src/self_evolve/locale.py](src/self_evolve/locale.py)

## 3. 配置

配置文件位置（项目级）：

- `<project-root>/.agents/self-evolve/config.jsonc`

当前配置核心字段：

- `plugin_id`
- `config_version`
- `promotion_threshold`
- `promotion_window_days`
- `min_task_count`
- `auto_promote`
- `inline_threshold`：自适应策略阈值（默认 20），≤ 阈值时内联全部规则，> 阈值时生成索引+分域文件

配置读写实现：

- [src/self_evolve/config.py](src/self_evolve/config.py)

## 4. 数据存储

所有数据统一存储在项目根目录 `.agents/` 下，不按智能体类型拆分：

学习条目存储位置（项目级）：

- `<project-root>/.agents/self-evolve/learnings/`

推广规则存储位置（项目级）：

- `<project-root>/.agents/self-evolve/rules.jsonc`

存储实现：

- [src/self_evolve/storage.py](src/self_evolve/storage.py)

## 5. Agent Skill 同步

同步模块采用**自适应分层策略**将推广规则输出为 Skill 文件，供所有 Agent 通过技能发现机制调用：

- **inline 策略**（规则数 ≤ `inline_threshold`）：所有规则内联到 `SKILL.md`
- **index 策略**（规则数 > `inline_threshold`）：`SKILL.md` 仅包含规则索引表，详细内容拆分到 `domains/*.md` 分域文件

输出文件：

- `.agents/skills/self-evolve/SKILL.md`：统一 Skill 文件（必有）
- `.agents/skills/self-evolve/catalog.json`：结构化规则目录（index 策略时生成）
- `.agents/skills/self-evolve/domains/*.md`：分域详细规则（index 策略时生成）
- `.agents/skills/self-evolve/find_rules.py`：零依赖本地搜索脚本（始终同步）

模板文件位于 [src/self_evolve/templates/](src/self_evolve/templates/)，搜索脚本位于 [src/self_evolve/scripts/](src/self_evolve/scripts/)。

同步实现：

- [src/self_evolve/sync.py](src/self_evolve/sync.py)

## 6. 核心概念

- **项目级进化**：所有数据存储在项目 `.agents/self-evolve/` 目录中，进化仅针对当前项目。
- **统一存储**：不按智能体类型拆分配置和输出，所有 Agent 共享同一份 Skill 文件。
- **学习条目**（Learning Entry）：结构化的经验记录。
- **模式识别**（Pattern Detection）：通过 `pattern_key` 精确匹配，关联相似条目。
- **推广**（Promotion）：满足门槛条件后提炼为永久规则。
- **同步**（Sync）：将推广规则输出为统一的 `.agents/skills/self-evolve/SKILL.md` 文件，采用自适应分层策略。
- **搜索**（Search）：按领域、标签或关键词搜索已推广规则。
- **一键进化**（Evolve）：自动完成 analyze → promote → sync 完整循环。
- **标签**（Tags）：学习条目和推广规则支持 `tags` 标签列表，推广时自动聚合来源条目的标签。
- **自适应策略**：根据规则数量自动选择 inline 或 index 策略，类似图书馆找书逻辑（分类 → 标签 → 标题 → 目录 → 线索）。

## 7. 业务规则

- 学习条目按单文件存储在 `.agents/self-evolve/learnings/` 中。
- 学习 ID 格式为 `L-YYYYMMDD-NNN`，自动递增。
- 推广规则 ID 格式为 `R-NNN`，自动递增。
- 模式识别采用 `pattern_key` 精确匹配。
- 推广条件须同时满足：`recurrence_count >= threshold`、`len(task_ids) >= min_task_count`。
- 同步输出为 `.agents/skills/self-evolve/SKILL.md` 独占文件，每次同步完整覆写。
- `capture` 支持 `--tags` 参数为学习条目附加标签。
- `search` 命令支持 `--domain`、`--tag`、`--keyword`、`--stats`、`--detail` 组合查询。
- 同步策略由 `inline_threshold` 配置控制，也可通过 `sync --strategy` 手动指定。

## 8. 修改本插件时重点验证

- `init` 是否正确创建 `.agents/self-evolve/` 目录和配置
- `capture` 是否正确在项目本地生成唯一 ID 并存储条目
- `list` 是否正确按状态/领域/优先级过滤
- `analyze` 是否正确识别模式、关联条目、递增计数
- `promote` 是否正确检查推广条件并生成规则
- `sync` 是否正确生成 `.agents/skills/self-evolve/SKILL.md`（含 YAML frontmatter）
- `sync` 在不同策略（inline/index）下是否正确生成对应文件
- `search` 是否正确按领域、标签、关键词过滤
- `evolve` 是否正确执行完整进化循环
- `status` 是否正确统计各维度数据
- 中英文下的 `--help`、warning/error、状态输出是否保持一致

相关测试：

- [tests/test_self_evolve_cli.py](tests/test_self_evolve_cli.py)
- [tests/test_self_evolve_logic.py](tests/test_self_evolve_logic.py)
