# AGENTS.md 分层重构 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将单一根目录 `AGENTS.md` 重构为四层分工结构，保留根目录全局规则与总架构摘要，并把 core、插件共享规则、单插件业务规则分别下沉到各自目录。

**Architecture:** 采用“父级继承、子级补充”的目录化文档模型。根目录负责全局规范和导航，`src/agent_kit/AGENTS.md` 负责 core，`packages/AGENTS.md` 负责插件共享协议，`packages/skills-link/AGENTS.md` 负责插件业务边界；所有文档路径统一使用相对路径。

**Tech Stack:** Markdown, git, rg, find

---

## Chunk 1: 文档结构重排

### Task 1: 盘点当前 AGENTS 文档与相关目录

**Files:**
- Modify: `docs/superpowers/plans/2026-03-17-agents-md-layering.md`
- Verify: `AGENTS.md`
- Verify: `src/agent_kit/`
- Verify: `packages/`
- Verify: `packages/skills-link/`

- [ ] **Step 1: 记录当前文档与目录现状**

Run:

```bash
find . -maxdepth 3 -name AGENTS.md | sort
find src/agent_kit packages/skills-link -maxdepth 2 -type f | sort
```

Expected:

- 只有根目录 `AGENTS.md`
- `src/agent_kit/` 与 `packages/skills-link/` 已存在，可作为落点

- [ ] **Step 2: 检查根目录 `AGENTS.md` 当前内容范围**

Run:

```bash
sed -n '1,260p' AGENTS.md
```

Expected:

- 能看到当前根文档同时包含全局规则、core 细节、插件细节
- 可以明确哪些内容需要下沉

- [ ] **Step 3: 提交一次盘点结论到工作记录**

在当前任务记录中标注：

- 根文档保留项
- 下沉到 `src/agent_kit/AGENTS.md` 的项
- 下沉到 `packages/AGENTS.md` 的项
- 下沉到 `packages/skills-link/AGENTS.md` 的项

### Task 2: 精简根目录 `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: 先写根文档的精简版提纲**

提纲应只包含：

```text
1. 全局语言与提交规范
2. 项目总体架构摘要
3. 顶层目录导航
4. AGENTS.md 分层继承规则
5. 指向 src/agent_kit/AGENTS.md 与 packages/AGENTS.md
```

- [ ] **Step 2: 删除不应继续放在根目录的局部细节**

删除或下沉以下内容：

- core 的详细实现边界
- 插件协议的详细条目
- `skills-link` 的业务规则
- 某个具体插件的测试细节

- [ ] **Step 3: 保留一小段总体架构摘要**

根文档摘要至少说明：

- `agent-kit` 是统一 CLI 入口
- core 负责插件管理与命令转发
- 插件运行在独立环境
- 当前第一方插件为 `skills-link`

- [ ] **Step 4: 统一根文档内所有路径为相对路径**

示例：

```md
[src/agent_kit/AGENTS.md](src/agent_kit/AGENTS.md)
[packages/AGENTS.md](packages/AGENTS.md)
```

- [ ] **Step 5: 人工检查根文档没有再次膨胀**

Run:

```bash
sed -n '1,220p' AGENTS.md
```

Expected:

- 内容明显短于当前版本
- 更像导航与总规则，不再承担局部说明职责

### Task 3: 新增 `src/agent_kit/AGENTS.md`

**Files:**
- Create: `src/agent_kit/AGENTS.md`

- [ ] **Step 1: 写入继承声明与关键提醒**

文件开头应包含：

```md
本目录继承根目录 `AGENTS.md` 的全局规则，本文只补充 core 相关约束。
```

并额外强调：

- 不要回退到 in-process 插件模型
- 修改注册表时同步两个官方注册表文件

- [ ] **Step 2: 写入 core 的职责边界**

至少覆盖：

- CLI 命令模型
- `PluginManager` 职责
- 注册表加载与缓存规则
- 配置/数据/缓存路径规则
- 安装、更新、运行时校验要点

- [ ] **Step 3: 写入 core 相关测试导航**

至少包含：

- `tests/test_core_cli.py`
- `tests/test_plugin_manager.py`

- [ ] **Step 4: 检查路径都为相对路径**

Run:

```bash
sed -n '1,240p' src/agent_kit/AGENTS.md
```

Expected:

- 所有路径都是相对路径
- 内容只关注 core，不混入插件业务细节

## Chunk 2: 插件层规则下沉

### Task 4: 新增 `packages/AGENTS.md`

**Files:**
- Create: `packages/AGENTS.md`

- [ ] **Step 1: 写入继承声明与共享规则**

至少说明：

- 继承根目录规则
- 本文只补充所有插件共享约束

- [ ] **Step 2: 写入插件命名规范**

至少包含：

- 插件分发名使用短名称
- 默认不要再添加 `agent-kit-` 前缀
- Python 模块名使用下划线形式
- `plugin_id` 应与对外命令名保持一致

- [ ] **Step 3: 写入统一协议要求**

至少包含：

- 必须提供 `agent-kit-plugin`
- 必须支持 `--plugin-metadata`
- 必须提供 `config_version`
- 配置文件使用 `config.jsonc`

- [ ] **Step 4: 写入新增插件 checklist**

至少包含：

- 包目录
- script
- metadata
- registry 条目
- 测试
- 局部 `AGENTS.md`

- [ ] **Step 5: 检查内容不要混入某个插件的业务细节**

Run:

```bash
sed -n '1,240p' packages/AGENTS.md
```

Expected:

- 内容是所有插件共享规则
- 没有 `skills-link` 的专属业务行为描述

### Task 5: 新增 `packages/skills-link/AGENTS.md`

**Files:**
- Create: `packages/skills-link/AGENTS.md`

- [ ] **Step 1: 写入继承声明与插件目标**

至少说明：

- 继承上级 `AGENTS.md`
- 本文只补充 `skills-link` 的业务规则
- 本插件负责将本地 skills 目录按目录粒度链接到目标目录

- [ ] **Step 2: 写入命令与配置说明**

至少覆盖：

- `init`
- `list`
- `link`
- `unlink`
- `status`
- 配置文件位置与字段

- [ ] **Step 3: 写入业务边界**

至少覆盖：

- 只识别包含 `SKILL.md` 的直接子目录
- 只按目录粒度处理
- 不覆盖冲突目标
- `unlink` 只删除受管软链接
- 不支持 Windows

- [ ] **Step 4: 写入插件测试导航**

至少包含：

- `packages/skills-link/tests/test_skill_link_cli.py`
- `packages/skills-link/tests/test_skill_link_logic.py`

- [ ] **Step 5: 检查局部文档只写插件自己的内容**

Run:

```bash
sed -n '1,260p' packages/skills-link/AGENTS.md
```

Expected:

- 内容是插件业务说明
- 没有 core 级实现细节

### Task 6: 做最终一致性验证

**Files:**
- Verify: `AGENTS.md`
- Verify: `src/agent_kit/AGENTS.md`
- Verify: `packages/AGENTS.md`
- Verify: `packages/skills-link/AGENTS.md`

- [ ] **Step 1: 检查 AGENTS 文件分层是否齐全**

Run:

```bash
find . -maxdepth 3 -name AGENTS.md | sort
```

Expected:

- 出现这四个文件：
  - `AGENTS.md`
  - `src/agent_kit/AGENTS.md`
  - `packages/AGENTS.md`
  - `packages/skills-link/AGENTS.md`

- [ ] **Step 2: 检查 Markdown 链接没有绝对路径**

Run:

```bash
rg -n "/Users/|\\]\\(/" AGENTS.md src/agent_kit/AGENTS.md packages/AGENTS.md packages/skills-link/AGENTS.md
```

Expected:

- 无输出

- [ ] **Step 3: 人工检查父子职责边界**

核对结论：

- 根目录只保留全局规则、摘要、导航
- `src/agent_kit/AGENTS.md` 只写 core
- `packages/AGENTS.md` 只写插件共享协议
- `packages/skills-link/AGENTS.md` 只写插件业务规则

- [ ] **Step 4: 提交**

Run:

```bash
git add AGENTS.md src/agent_kit/AGENTS.md packages/AGENTS.md packages/skills-link/AGENTS.md
git commit -m "重构 AGENTS 文档分层结构"
```

Expected:

- 提交成功
- 提交信息为中文
