# self-evolve SKILL.md 生成优化设计

## 概述

重构 self-evolve 插件的 SKILL.md 生成系统，解决三个核心问题：
1. 生成的 SKILL.md 格式不符合 Agent Skill 规范（缺少 frontmatter、标准分区）
2. 随项目规模增长的上下文膨胀问题
3. Agent 消费侧需项目自包含（不依赖插件即可检索规则）

## 方案：自适应分层 + 渐进式披露

### 模板化生成
- 模板文件放在 `src/self_evolve/templates/`，使用 `string.Template` 渲染
- 生成的 SKILL.md 包含标准 YAML frontmatter、中文内容、规范分区

### 自适应策略
- 规则 ≤ 20（可配置）：内联模式，规则直接嵌入 SKILL.md
- 规则 > 20：索引模式，SKILL.md 只保留概览表格，详情拆分到 `domains/*.md`

### 项目自包含
- `scripts/find_rules.py`：纯 stdlib 检索脚本，sync 时自动复制到项目
- `catalog.json`：结构化全量索引，供脚本和 Agent 读取

### 数据模型扩展
- `LearningEntry` / `PromotedRule` 新增 `tags` 字段
- `PromotedRule` 新增 `title` 字段
- promote 时自动聚合 tags

### 新增 CLI
- `search` 命令：按域/标签/关键词查询规则

详细设计见前序对话记录。
