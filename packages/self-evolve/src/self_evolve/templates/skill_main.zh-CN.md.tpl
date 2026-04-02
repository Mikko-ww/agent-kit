---
name: self-evolve
description: "${description}"
---

# 项目知识规则

该文件由 `self-evolve` 生成，仅包含已批准的正式项目规则。

${rules_section}

## 反思注入

当用户要求你总结经验、提取规则或注入知识时，按以下步骤执行：

### 1. 检查已有规则

先运行以下命令，确认是否已有相似规则：

```bash
python .agents/skills/self-evolve/scripts/list_rules.py --keyword "<关键词>"
```

### 2. 分析并提取

从当前对话上下文中提取以下结构化信息：

- **domain**：知识所属领域（如 `debugging`、`testing`、`architecture`、`performance`）
- **title**：简短标题（20 字以内）
- **statement**：规则的精确描述——必须是可执行的祈使句或明确约束，不要用模糊表述
- **rationale**：为什么需要这条规则——必须说明不遵循时的具体后果
- **tags**：相关标签

每条规则只表达一个独立知识点。如果需要多条规则，分别执行。

### 3. 写入规则

```bash
python .agents/skills/self-evolve/scripts/add_rule.py \
  --title "<标题>" \
  --statement "<规则描述>" \
  --rationale "<原因>" \
  --domain <领域> \
  --tag <标签1> \
  --tag <标签2>
```

### 4. 提醒用户审核

告知用户新规则已写入 `.agents/self-evolve/rules/` 目录，建议通过 `git diff` 审核后提交。

规则生效需要运行：

```bash
agent-kit self-evolve sync
```

## 规则管理

| 操作 | 命令 |
|------|------|
| 列出规则 | `python .agents/skills/self-evolve/scripts/list_rules.py` |
| 搜索规则 | `python .agents/skills/self-evolve/scripts/find_rules.py --keyword "..."` |
| 编辑规则 | `python .agents/skills/self-evolve/scripts/edit_rule.py <rule-id> --statement "..."` |
| 停用规则 | `python .agents/skills/self-evolve/scripts/retire_rule.py <rule-id>` |
| 同步到 Skill | `agent-kit self-evolve sync` |

_最近同步时间：${last_synced}_
