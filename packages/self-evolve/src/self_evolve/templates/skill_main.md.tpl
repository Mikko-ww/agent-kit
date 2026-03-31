---
name: self-evolve
description: "${description}"
---

# 项目自进化规则

本文件由 self-evolve 自动生成，包含从项目实践中提炼的经验规则。

${rules_section}

## 如何使用

### 查找规则

运行项目内检索脚本（无需安装插件）：

```bash
python .agents/skills/self-evolve/scripts/find_rules.py --domain <领域名>
python .agents/skills/self-evolve/scripts/find_rules.py --keyword "关键词"
python .agents/skills/self-evolve/scripts/find_rules.py --tag <标签>
python .agents/skills/self-evolve/scripts/find_rules.py --stats
```

或通过插件 CLI：

```bash
agent-kit self-evolve search --domain <领域名>
agent-kit self-evolve search --keyword "关键词"
```

### 捕获新学习

```bash
agent-kit self-evolve capture \
  --summary "简要描述" \
  --domain "debugging|testing|architecture|performance|security|style" \
  --pattern-key "unique-pattern-identifier" \
  --task-id "current-task-id" \
  --tags "tag1,tag2"
```

### 运行进化循环

```bash
agent-kit self-evolve evolve
```

_最近同步: ${last_synced}_
