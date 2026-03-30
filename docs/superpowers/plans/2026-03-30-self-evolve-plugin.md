# self-evolve 自我进化插件 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `self-evolve` 插件，提供结构化的学习捕获、模式识别、规则推广和技能提取能力，让 Agent 能从经验中持续进化。

**Architecture:** 遵循现有插件架构模式（`skills-link` / `opencode-env-switch`），使用 Typer CLI + JSONC 配置 + 文件存储。数据存储在 `data_root/plugins/self-evolve/`，配置存储在 `config_root/plugins/self-evolve/`。

**Tech Stack:** Python 3.11+, Typer, Questionary, JSONC, pytest, hatchling

---

## Chunk 1: 插件目录与基础模块

### Task 1: 创建插件目录结构

**Files:**
- Create: `packages/self-evolve/pyproject.toml`
- Create: `packages/self-evolve/src/self_evolve/__init__.py`
- Create: `packages/self-evolve/src/self_evolve/jsonc.py`
- Create: `packages/self-evolve/src/self_evolve/locale.py`
- Create: `packages/self-evolve/src/self_evolve/messages.py`

- [ ] **Step 1: 创建 `pyproject.toml`**

```toml
[project]
name = "self-evolve"
version = "0.1.0"
description = "Self-evolving agent skill toolkit for agent-kit."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "questionary>=2.0,<3.0",
    "typer>=0.12,<1.0",
]

[project.scripts]
agent-kit-plugin = "self_evolve.plugin_cli:main"

[build-system]
requires = ["hatchling>=1.27,<2.0"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: 创建 `__init__.py` 定义常量**
- [ ] **Step 3: 复制 `jsonc.py` 工具模块**
- [ ] **Step 4: 创建 `locale.py` 语言解析模块**
- [ ] **Step 5: 创建 `messages.py` 多语言消息**

### Task 2: 实现数据模型与存储

**Files:**
- Create: `packages/self-evolve/src/self_evolve/models.py`
- Create: `packages/self-evolve/src/self_evolve/storage.py`

- [ ] **Step 1: 定义 `LearningEntry` 数据模型**
- [ ] **Step 2: 定义 `PromotedRule` 数据模型**
- [ ] **Step 3: 实现学习条目的文件存储（保存/加载/列表/删除）**
- [ ] **Step 4: 实现规则库的文件存储**

### Task 3: 实现配置管理

**Files:**
- Create: `packages/self-evolve/src/self_evolve/config.py`

- [ ] **Step 1: 定义 `SelfEvolveConfig` 数据类**
- [ ] **Step 2: 实现 `load_config` / `save_config` 含版本校验**

## Chunk 2: 核心业务逻辑

### Task 4: 实现核心逻辑

**Files:**
- Create: `packages/self-evolve/src/self_evolve/logic.py`

- [ ] **Step 1: 实现学习捕获逻辑（`capture_learning`）**
- [ ] **Step 2: 实现学习列表与过滤逻辑（`list_learnings`）**
- [ ] **Step 3: 实现模式分析逻辑（`analyze_patterns`）**
- [ ] **Step 4: 实现推广判断与执行逻辑（`check_promotion_eligibility`、`promote_learning`）**
- [ ] **Step 5: 实现技能提取逻辑（`extract_skill`）**
- [ ] **Step 6: 实现状态概览逻辑（`get_evolution_status`）**

## Chunk 3: CLI 入口

### Task 5: 实现 CLI

**Files:**
- Create: `packages/self-evolve/src/self_evolve/plugin_cli.py`

- [ ] **Step 1: 搭建 Typer app + `--plugin-metadata` 回调**
- [ ] **Step 2: 实现 `wizard` 命令**
- [ ] **Step 3: 实现 `capture` 命令**
- [ ] **Step 4: 实现 `list` 命令**
- [ ] **Step 5: 实现 `analyze` 命令**
- [ ] **Step 6: 实现 `promote` 命令**
- [ ] **Step 7: 实现 `extract-skill` 命令**
- [ ] **Step 8: 实现 `status` 命令**

## Chunk 4: 文档与注册

### Task 6: 创建文档并注册插件

**Files:**
- Create: `packages/self-evolve/AGENTS.md`
- Create: `packages/self-evolve/README.md`
- Modify: `registry/official.json`
- Modify: `src/agent_kit/official_registry.json`
- Modify: `pyproject.toml`（根目录，workspace 配置）

- [ ] **Step 1: 编写 `AGENTS.md`**
- [ ] **Step 2: 编写 `README.md`**
- [ ] **Step 3: 在两个 registry 文件中注册 `self-evolve`**
- [ ] **Step 4: 更新根目录 `pyproject.toml` workspace 配置**

## Chunk 5: 测试

### Task 7: 编写测试

**Files:**
- Create: `packages/self-evolve/tests/test_self_evolve_logic.py`
- Create: `packages/self-evolve/tests/test_self_evolve_cli.py`

- [ ] **Step 1: 编写配置加载/保存测试**
- [ ] **Step 2: 编写存储层测试**
- [ ] **Step 3: 编写学习捕获逻辑测试**
- [ ] **Step 4: 编写模式分析逻辑测试**
- [ ] **Step 5: 编写推广逻辑测试**
- [ ] **Step 6: 编写技能提取逻辑测试**
- [ ] **Step 7: 编写 CLI 命令测试**
- [ ] **Step 8: 编写中英文输出测试**

## Chunk 6: 验证与收尾

### Task 8: 完整验证

- [ ] **Step 1: 运行插件自身测试**

Run: `uv run pytest packages/self-evolve/tests/ -v`

- [ ] **Step 2: 运行全量测试确认无回归**

Run: `uv run pytest`

- [ ] **Step 3: 检查 diff 质量**

Run: `git diff --check`

- [ ] **Step 4: 使用 `plugin-release-followup` skill 完成发布收尾**
