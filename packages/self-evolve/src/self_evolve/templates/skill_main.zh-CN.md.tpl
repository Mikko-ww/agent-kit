---
name: self-evolve
description: "${description}"
---

# 项目知识规则

该文件由 `self-evolve` 生成，仅包含已批准的正式项目规则。

${rules_section}

## 工作流

1. 记录 session：

```bash
agent-kit self-evolve session record --summary "..." --domain debugging --outcome success --lesson "..."
```

2. 运行 candidate 检测：

```bash
agent-kit self-evolve detect run
```

3. 审核 candidate，或直接新增正式 rule：

```bash
agent-kit self-evolve candidate list
agent-kit self-evolve rule add --title "..." --statement "..." --rationale "..." --domain debugging
```

_最近同步时间：${last_synced}_
