# self-evolve 插件可优化建议

## 概述

基于对 `self-evolve` v5.0.2 的完整代码审查，本文档整理了当前插件在架构、功能、脚本层、同步机制、数据一致性和 Agent 消费体验等方面的可优化方向。每条建议均标注优先级（P1 重要 / P2 改进 / P3 远期）和实现难度（低 / 中 / 高），并说明当前现状与建议改动。当前版本不存在需要紧急修复的 P0 级问题。

---

## 1. 规则质量保障

### 1.1 status 字段缺少枚举约束（P1 / 低）

**现状：** `KnowledgeRule.status` 是自由字符串，任何值都能写入。`models.py` 中没有对 `status` 做值域校验，脚本层也未统一约束。如果误写成 `actve` 或 `Active`，sync 会静默丢失该规则。

**建议：** 在 `models.py` 中定义 `STATUS_ACTIVE = "active"` 和 `STATUS_RETIRED = "retired"` 常量，在 `from_dict` 中校验 status 值不在白名单时抛出 `ValueError` 或回退到默认值。脚本层的 `retire_rule.py` 和 `add_rule.py` 统一引用常量。

### 1.2 字段验证不完整（P2 / 低）

**现状：** 脚本层只检查字段是否为空字符串（`not args.title.strip()`），但没有长度限制、特殊字符过滤或格式校验。`domain` 也没有白名单或推荐值约束。

**建议：**

- 为 `title` 增加最大长度限制（如 100 字符），避免生成过长的 SKILL.md 标题行。
- 为 `domain` 增加格式建议（仅允许小写字母、数字和连字符），防止大小写不一致导致 domain 分裂（如 `Debugging` 和 `debugging` 被视为不同域）。
- 为 `tags` 增加单标签最大长度限制。

### 1.3 重复检测仅为警告，允许创建相同指纹规则（P2 / 低）

**现状：** `add_rule.py` 中的 `_check_duplicate` 检测到重复时只在 stderr 打印警告，但仍会继续创建规则。这可能导致知识库中出现语义重复的规则。

**建议：** 增加 `--force` 参数（默认不启用），未指定 `--force` 时重复指纹直接报错退出；指定 `--force` 时保留当前的警告行为。这样默认路径更安全，同时保留覆盖能力。

### 1.4 revision_of 字段未被系统使用（P2 / 中）

**现状：** `KnowledgeRule` 包含 `revision_of` 字段，`edit_rule.py` 也可以修改规则内容，但修改后不会自动记录修订关系。`revision_of` 始终为空字符串，形同虚设。

**建议：** 在 `edit_rule.py` 中，当修改了 `statement` 或 `rationale` 等核心字段时：

1. 将原始规则状态改为 `retired`。
2. 创建一条新规则，`revision_of` 指向原 ID。
3. 这样可以保留完整的修订链，同时保持 Git diff 可追溯。

或者，如果暂时不需要修订链功能，考虑从模型中移除 `revision_of` 字段以避免混淆。

---

## 2. 同步机制优化

### 2.1 全量重建无增量同步（P2 / 中）

**现状：** 每次调用 `sync_skill()` 都完整重新渲染 SKILL.md、catalog.json 和所有 domain 文件，即使没有任何规则变化。对于规则数量较多的项目，这会产生不必要的文件写入和 Git diff 噪音（如 `last_synced` 日期变化）。

**建议：**

- 在写入前比较新旧文件内容（排除 `last_synced` 字段），内容一致则跳过写入。
- 或在 catalog.json 中记录规则的内容哈希，sync 时仅在规则实际变化时更新输出文件。
- 最低限度优化：如果只有 `last_synced` 变了而规则内容不变，不更新文件。

### 2.2 catalog.json 与规则文件可能不一致（P1 / 中）

**现状：** 脚本（`add_rule.py`、`edit_rule.py`、`retire_rule.py`）直接读写 `.agents/self-evolve/rules/` 下的 JSON 文件，但 `catalog.json` 和 `SKILL.md` 只在用户手动执行 `sync` 后才更新。这导致 `find_rules.py`（读 catalog.json）可能返回过期数据。

**建议：**

- **方案 A（推荐）**：在 `add_rule.py`、`edit_rule.py`、`retire_rule.py` 执行成功后，自动触发轻量级的 catalog.json 增量更新（仅更新 rules 列表和 summary，不重新渲染 SKILL.md）。
- **方案 B**：在 `find_rules.py` 中增加 `--live` 选项，直接从 rules 目录读取而非 catalog.json，确保数据实时性。
- **方案 C**：在 `find_rules.py` 输出末尾增加提示，告知用户 catalog.json 的最后同步时间，提醒必要时运行 sync。

### 2.3 脚本复制部分失败时无法感知（P2 / 低）

**现状：** `_sync_scripts()` 中单个脚本复制失败会打印 stderr 警告并继续，但 `SyncResult` 不包含失败信息，CLI 层的成功消息也不区分全成功/部分失败。

**建议：** 在 `SyncResult` 中增加 `failed_scripts: list[str]` 字段，CLI 输出中对有失败的情况给出明确的警告提示。

---

## 3. 脚本层健壮性

### 3.1 路径解析硬编码且无校验（P1 / 中）

**现状：** 所有脚本通过相对路径推算 rules 目录位置：

```python
def _resolve_rules_dir(script_dir: Path) -> Path:
    agents_dir = script_dir.parent.parent.parent  # scripts/ → self-evolve/ → skills/ → .agents/
    return agents_dir / "self-evolve" / "rules"
```

如果脚本被拷贝到其他位置、通过符号链接执行，或项目目录结构调整，路径推算就会断裂。当前没有任何校验机制。

**建议：**

- 在推算后检查 rules 目录是否存在，不存在时给出明确的错误提示并建议正确的使用方式。
- 考虑支持环境变量 `SELF_EVOLVE_RULES_DIR` 作为备用路径来源，提升脚本的部署灵活性。

### 3.2 脚本目录创建异常未处理（P2 / 低）

**现状：** `add_rule.py` 中 `rules_dir.mkdir(parents=True, exist_ok=True)` 如果因权限问题失败，会直接抛出未捕获的 `OSError`，用户看到的是 Python traceback 而非友好的错误消息。

**建议：** 用 try-except 包裹 mkdir 调用，捕获 `OSError` 并输出友好的错误提示（如"无法创建规则目录，请检查权限"）。

### 3.3 脚本缺少 `--help` 输出优化（P3 / 低）

**现状：** 脚本使用 `argparse`，`--help` 输出是标准的 argparse 格式，没有用法示例。对于 Agent 来说，一个带示例的 help 输出更容易正确调用。

**建议：** 在各脚本的 `ArgumentParser` 中增加 `epilog` 参数，提供典型调用示例。

---

## 4. Agent 消费体验

### 4.1 反思注入指令缺少错误处理指引（P1 / 低）

**现状：** SKILL.md 中的反思注入指令引导 Agent 执行四步操作（查重 → 提取 → 写入 → 提醒审核），但没有告诉 Agent 在各步骤失败时应如何处理。例如 `add_rule.py` 报告重复时，Agent 应该怎么做？

**建议：** 在模板的反思注入指令中增加错误处理步骤：

- 如果查重发现相似规则，应先展示给用户确认是否仍需添加。
- 如果 `add_rule.py` 返回非零退出码，应告知用户具体错误并建议修正。
- 如果规则写入成功但 sync 失败，应提示手动重试 sync。

### 4.2 SKILL.md 缺少规则质量标准说明（P2 / 低）

**现状：** 反思注入指令要求 Agent 提取 title/statement/rationale/domain/tags，但没有说明什么样的规则是"好规则"。Agent 可能生成过于宽泛或过于具体的规则。

**建议：** 在模板中增加简短的规则质量标准（1-2 句即可），例如：

- statement 应该是具体的、可执行的指令，而非笼统的原则。
- rationale 应该说明不遵循时的具体后果，而非空泛的理由。
- 一条规则只聚焦一个要点，避免合并多个不相关的经验。

### 4.3 find_rules.py 缺少模糊匹配能力（P3 / 中）

**现状：** `find_rules.py` 的 `--keyword` 参数是简单的子串匹配（`keyword.lower() in text.lower()`），不支持多关键词组合查询或模糊匹配。

**建议：** 支持多关键词查询（如 `--keyword "环境" --keyword "校验"`，取交集），提升 Agent 查重时的召回率。

---

## 5. 数据一致性与可靠性

### 5.1 规则写入非原子操作（P2 / 中）

**现状：** `storage.py` 的 `save_rule` 直接调用 `path.write_text()`。如果写入过程中进程被中断（如系统崩溃、信号中断），可能留下半写的 JSON 文件，后续加载时会因 `JSONDecodeError` 而被跳过。

**建议：** 采用"写临时文件 + 原子 rename"模式：

```python
tmp = path.with_suffix(".tmp")
tmp.write_text(content, encoding="utf-8")
tmp.rename(path)  # POSIX 上是原子操作；Windows 上 Python 3.12+ 的 Path.rename 也是原子的
```

注意：`Path.rename()` 在 Python 3.12+ 的 Windows 上已使用 `ReplaceFile` API 实现原子替换。对于更早版本的 Windows 兼容性，可改用 `os.replace()` 作为跨平台替代。

### 5.2 list_rules 大规模文件场景性能隐患（P3 / 中）

**现状：** `list_rules()` 每次调用都遍历 `rules/` 目录下的所有 `R-*.json` 文件并逐个解析。对于规则数量超过几百条的项目，这个 O(n) 全量加载可能变慢。

**建议：** 短期可以暂不优化（v5 目标用户通常规则数 < 100）。中期如果规则量增长，可以考虑引入轻量级索引文件（类似 catalog.json 但放在 rules 目录内部），记录 ID → status 的快速映射，减少不必要的文件解析。

---

## 6. CLI 与用户体验

### 6.1 sync 成功后无变更摘要（P2 / 低）

**现状：** sync 命令只输出 `"Sync completed: {rules_count} active rules, strategy={strategy}"`。用户无法直观知道本次 sync 相比上次有哪些变化（新增了几条规则、退役了几条等）。

**建议：** 输出更详细的变更摘要，例如：

```
Sync completed: 8 active rules, strategy=inline
  Added: 2 rules (R-007, R-008)
  Retired: 1 rule (R-003)
  Unchanged: 5 rules
```

实现方式：sync 前先读取上一版 catalog.json 的规则列表，与本次待同步的规则列表对比。

### 6.2 init 命令缺少 `--language` 参数（P2 / 低）

**现状：** init 命令的模板语言只能通过交互式 prompt 选择或通过 `AGENT_KIT_LANG` 环境变量预设。在自动化脚本或 CI 环境中不方便。

**建议：** 增加 `--language` 命令行参数，允许 `agent-kit self-evolve init --language zh-CN` 直接指定，跳过交互式 prompt。

### 6.3 status 输出信息过于简略（P3 / 低）

**现状：** status 命令只输出规则数量和状态分布（`Rules: total=5, active=4, retired=1`），没有其他有用信息（如最近修改时间、domain 分布、是否需要 sync 等）。

**建议：** 增加以下信息：

- Domain 分布（每个 domain 有多少 active 规则）
- 最近添加/修改的规则 ID 和时间
- 当前 Skill 输出策略（inline/index）
- 规则文件与 catalog.json 的同步状态（是否有未同步的变更）

---

## 7. 国际化与可扩展性

### 7.1 仅支持两种语言（P3 / 低）

**现状：** 模板和 CLI 文案仅支持 `en` 和 `zh-CN`，不支持其他语言。虽然当前用户群体以中英文为主，但架构上缺乏语言扩展机制。

**建议：** 短期无需增加新语言。但可以在模板加载逻辑中增加日志提示，当请求的语言不存在对应模板时，明确告知用户回退到了英文（当前是静默回退）。

### 7.2 模板中的 domain 示例硬编码（P3 / 低）

**现状：** SKILL.md 模板中的 domain 示例（`debugging`、`testing`、`architecture`、`performance`）是硬编码的。不同项目类型可能有不同的 domain 偏好。

**建议：** 在 sync 生成 SKILL.md 时，从已有规则中提取实际使用的 domain 列表，动态替换模板中的示例部分，让 Agent 更容易选择已有 domain 而非创建新的。

---

## 8. 测试覆盖度

### 8.1 缺少端到端集成测试（P2 / 中）

**现状：** 当前 32 个测试用例全部是单元测试或模块级测试。没有模拟完整用户工作流（init → 多次 add_rule → sync → find_rules → edit_rule → sync）的集成测试。

**建议：** 增加 1-2 个端到端测试用例，覆盖从初始化到规则管理到同步的完整流程，验证各模块协作的正确性。

### 8.2 缺少边界条件测试（P3 / 低）

**现状：** 没有针对大量规则（如 50+ 条）的测试。index 策略虽然有基本测试，但未验证多个 domain、大量规则下的渲染正确性和性能。

**建议：** 增加参数化测试，覆盖 inline/index 策略切换阈值附近的边界情况（如 19/20/21 条规则）。

---

## 建议优先级排序

按实施价值和成本综合排序：

| 优先级 | 编号 | 建议 | 难度 | 价值 |
|--------|------|------|------|------|
| **P1** | 2.2 | catalog.json 与规则文件一致性 | 中 | 高——直接影响 Agent 查重准确性 |
| **P1** | 3.1 | 脚本路径解析健壮性 | 中 | 高——影响脚本可用性 |
| **P1** | 1.1 | status 字段枚举约束 | 低 | 中——防止静默数据丢失 |
| **P1** | 4.1 | 反思注入指令错误处理 | 低 | 中——提升 Agent 自主修复能力 |
| **P2** | 1.3 | 重复检测默认报错 | 低 | 中——减少知识库噪音 |
| **P2** | 2.1 | 增量同步 | 中 | 中——减少 Git diff 噪音 |
| **P2** | 5.1 | 原子写入 | 中 | 中——提升数据可靠性 |
| **P2** | 6.1 | sync 变更摘要 | 低 | 中——改善用户体验 |
| **P2** | 6.2 | init --language 参数 | 低 | 低——支持自动化 |
| **P2** | 1.2 | 字段验证增强 | 低 | 低——提升数据质量 |
| **P2** | 1.4 | revision_of 字段用或删 | 中 | 低——减少概念混淆 |
| **P2** | 2.3 | 脚本复制失败感知 | 低 | 低——改善错误诊断 |
| **P2** | 4.2 | 规则质量标准说明 | 低 | 低——提升规则质量 |
| **P2** | 8.1 | 端到端集成测试 | 中 | 中——提升可维护性 |
| **P3** | 3.2 | 脚本目录创建异常处理 | 低 | 低 |
| **P3** | 3.3 | 脚本 --help 示例 | 低 | 低 |
| **P3** | 4.3 | find_rules 多关键词查询 | 中 | 低 |
| **P3** | 5.2 | 大规模规则性能 | 中 | 低——当前规模不需要 |
| **P3** | 6.3 | status 输出增强 | 低 | 低 |
| **P3** | 7.1 | 语言回退提示 | 低 | 低 |
| **P3** | 7.2 | domain 示例动态化 | 低 | 低 |
| **P3** | 8.2 | 边界条件测试 | 低 | 低 |

---

## 建议实施路线

### 第一批（短期，低风险高收益）

目标：解决数据安全和脚本可用性的基础问题。

- 1.1 status 字段枚举约束
- 3.1 脚本路径解析健壮性
- 4.1 反思注入指令错误处理
- 1.3 重复检测默认报错

### 第二批（中期，提升同步质量）

目标：改善 catalog.json 一致性和 sync 输出体验。

- 2.2 catalog.json 一致性保障
- 2.1 增量同步基础
- 6.1 sync 变更摘要
- 5.1 原子写入

### 第三批（远期，功能扩展）

目标：丰富 CLI 能力和测试覆盖。

- 6.2 init --language 参数
- 1.4 revision_of 决策
- 8.1 端到端集成测试
- 4.2 规则质量标准说明
