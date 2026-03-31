# self-evolve v5: Skill 驱动的极简知识流水线 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 self-evolve 从三层流水线（Session → Candidate → Rule）简化为 Agent 直接操作 Rule 的极简架构，Rule CRUD 由零依赖 Python 脚本驱动，SKILL.md 增加反思注入指令让 Agent 自主提取和录入规则。

**Architecture:** 移除 Session/Candidate 层，CLI 仅保留 `init`/`sync`/`status` 三个基础设施命令。Rule 的增删改查由 `scripts/` 目录下的独立 Python 脚本完成（纯 stdlib，零依赖），`sync` 时自动复制到项目 `.agents/skills/self-evolve/scripts/`。Skill 模板增加反思注入指令，引导 Agent 从对话上下文中提取结构化知识并调用脚本写入规则。人工审核通过 Git diff 完成。

**Tech Stack:** Python 3.11+, Typer (仅 CLI 层), argparse (脚本层), pytest, hatchling

---

## Chunk 1: 模型精简与脚本层

### Task 1: 精简数据模型

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/__init__.py`
- Modify: `packages/self-evolve/src/self_evolve/models.py`

- [ ] **Step 1: 升级 CONFIG_VERSION**

`__init__.py` 中将 `CONFIG_VERSION = 4` 改为 `CONFIG_VERSION = 5`，版本号从 `0.4.2` 改为 `0.5.0`。

```python
__version__ = "0.5.0"
PLUGIN_ID = "self-evolve"
API_VERSION = 1
CONFIG_VERSION = 5
```

- [ ] **Step 2: 精简 models.py**

删除 `SessionRecord`、`KnowledgeCandidate`、`KnowledgeIndex` 三个 dataclass 及其 `to_dict()`/`from_dict()` 方法，仅保留 `KnowledgeRule`。

保留的 `KnowledgeRule` 需要调整：移除 `source_session_ids` 和 `source_candidate_ids` 字段（v5 规则不再追溯 session/candidate 来源）。

精简后的 `models.py` 只包含一个 dataclass：

```python
@dataclass(slots=True)
class KnowledgeRule:
    id: str
    created_at: str
    status: str
    title: str
    statement: str
    rationale: str
    domain: str
    tags: list[str] = field(default_factory=list)
    revision_of: str = ""
```

- [ ] **Step 3: 验证改动编译通过**

Run: `cd packages/self-evolve && python -c "from self_evolve.models import KnowledgeRule; print('OK')"`
Expected: `OK`

---

### Task 2: 精简存储层

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/storage.py`

- [ ] **Step 1: 删除 session/candidate/index 相关函数**

从 `storage.py` 中删除以下函数：
- `save_session`, `load_session`, `list_sessions`
- `save_candidate`, `load_candidate`, `list_candidates`
- `save_index`, `load_index`

保留：`save_rule`, `load_rule`, `list_rules`, `_save_entity`, `_load_entity`, `_list_entities`

更新 import：移除 `from self_evolve.config import candidates_dir, indexes_dir, sessions_dir`，仅保留 `from self_evolve.config import rules_dir`。

移除 `from self_evolve.models import KnowledgeCandidate, KnowledgeIndex, SessionRecord`，仅保留 `from self_evolve.models import KnowledgeRule`。

---

### Task 3: 精简配置层

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/config.py`

- [ ] **Step 1: 简化 SelfEvolveConfig**

移除 `auto_accept_enabled` 和 `auto_accept_min_confidence` 字段：

```python
@dataclass(slots=True, frozen=True)
class SelfEvolveConfig:
    language: str | None = None
    inline_threshold: int = 20
```

- [ ] **Step 2: 移除 sessions/candidates/indexes 路径函数**

删除 `sessions_dir()`、`candidates_dir()`、`indexes_dir()` 函数。保留 `evolve_dir()`、`config_file_path()`、`rules_dir()`、`skill_dir()`。

- [ ] **Step 3: 更新 save_config 和 load_config**

`save_config` payload 中移除 `auto_accept_enabled`、`auto_accept_min_confidence`。

`load_config` 中移除对这两个字段的读取。CONFIG_VERSION 校验值从 4 改为 5。

- [ ] **Step 4: 更新旧版检测**

`_LEGACY_MARKERS` 元组中追加 `"sessions"` 和 `"candidates"`——v5 中这两个目录也视为旧布局。

```python
_LEGACY_MARKERS = ("learnings", "rules.jsonc", "sessions", "candidates")
```

---

### Task 4: 删除废弃模块

**Files:**
- Delete: `packages/self-evolve/src/self_evolve/session_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/candidate_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/detector.py`
- Delete: `packages/self-evolve/src/self_evolve/index_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/rule_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/ids.py`

- [ ] **Step 1: 删除以上 6 个文件**

这些模块的逻辑（ID 生成、fingerprint 计算、Rule CRUD）将迁移到独立脚本层（Task 5-8）。`ids.py` 和 `fingerprints.py` 的逻辑会内联到各脚本中。

> 注意：`fingerprints.py` 暂时保留，因为 `sync.py` 中可能引用（需确认）。实际上 `sync.py` 不直接使用 `fingerprints.py`，但为安全起见在 Task 12 sync 改造时再确定。如果 sync 不需要也一并删除。

---

### Task 5: 创建 add_rule.py 脚本

**Files:**
- Create: `packages/self-evolve/src/self_evolve/scripts/add_rule.py`

- [ ] **Step 1: 实现 add_rule.py**

零依赖 Python 脚本（仅 stdlib），功能：
1. 从 `Path(__file__).resolve()` 推算 `rules_dir`：`scripts/ → skills/self-evolve/ → .agents/ → self-evolve/rules/`
2. 扫描 `rules_dir` 现有 `R-NNN.json` 文件，取最大序号 +1 生成新 ID
3. 计算 fingerprint（`domain:normalized-statement`），扫描已有规则检查重复——重复时输出警告但不阻止
4. 写入 `R-NNN.json` 文件
5. 打印创建结果

```python
#!/usr/bin/env python3
"""Add a new rule to the self-evolve knowledge base. Zero dependencies."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    """从 .agents/skills/self-evolve/scripts/ 推算到 .agents/self-evolve/rules/"""
    agents_dir = script_dir.parent.parent.parent  # scripts/ → self-evolve/ → skills/ → .agents/
    return agents_dir / "self-evolve" / "rules"


def _next_rule_id(rules_dir: Path) -> str:
    max_seq = 0
    if rules_dir.exists():
        for path in rules_dir.glob("R-*.json"):
            try:
                seq = int(path.stem.split("-", 1)[1])
            except (ValueError, IndexError):
                continue
            max_seq = max(max_seq, seq)
    return f"R-{max_seq + 1:03d}"


def _build_fingerprint(domain: str, statement: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", statement.lower()).strip("-")
    return f"{domain}:{normalized}"


def _check_duplicate(rules_dir: Path, fingerprint: str) -> str | None:
    if not rules_dir.exists():
        return None
    for path in rules_dir.glob("R-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        existing_fp = _build_fingerprint(
            str(data.get("domain", "")), str(data.get("statement", ""))
        )
        if existing_fp == fingerprint and data.get("status") == "active":
            return str(data.get("id", path.stem))
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a new rule to self-evolve.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--statement", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--tag", action="append", default=[])
    args = parser.parse_args()

    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    rules_dir.mkdir(parents=True, exist_ok=True)

    fingerprint = _build_fingerprint(args.domain, args.statement)
    existing = _check_duplicate(rules_dir, fingerprint)
    if existing:
        print(f"Warning: similar active rule exists: {existing}", file=sys.stderr)

    rule_id = _next_rule_id(rules_dir)
    rule = {
        "id": rule_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "title": args.title,
        "statement": args.statement,
        "rationale": args.rationale,
        "domain": args.domain,
        "tags": sorted(set(args.tag)),
        "revision_of": "",
    }

    path = rules_dir / f"{rule_id}.json"
    path.write_text(json.dumps(rule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created rule: {rule_id} -> {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证脚本语法正确**

Run: `python -c "import ast; ast.parse(open('packages/self-evolve/src/self_evolve/scripts/add_rule.py').read()); print('OK')"`
Expected: `OK`

---

### Task 6: 创建 edit_rule.py 脚本

**Files:**
- Create: `packages/self-evolve/src/self_evolve/scripts/edit_rule.py`

- [ ] **Step 1: 实现 edit_rule.py**

```python
#!/usr/bin/env python3
"""Edit an existing rule. Zero dependencies."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    agents_dir = script_dir.parent.parent.parent
    return agents_dir / "self-evolve" / "rules"


def main() -> None:
    parser = argparse.ArgumentParser(description="Edit an existing self-evolve rule.")
    parser.add_argument("rule_id")
    parser.add_argument("--title")
    parser.add_argument("--statement")
    parser.add_argument("--rationale")
    parser.add_argument("--domain")
    parser.add_argument("--tag", action="append")
    args = parser.parse_args()

    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    path = rules_dir / f"{args.rule_id}.json"
    if not path.exists():
        print(f"Rule not found: {args.rule_id}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    if args.title is not None:
        data["title"] = args.title
    if args.statement is not None:
        data["statement"] = args.statement
    if args.rationale is not None:
        data["rationale"] = args.rationale
    if args.domain is not None:
        data["domain"] = args.domain
    if args.tag is not None:
        data["tags"] = sorted(set(args.tag))

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated rule: {args.rule_id}")


if __name__ == "__main__":
    main()
```

---

### Task 7: 创建 retire_rule.py 脚本

**Files:**
- Create: `packages/self-evolve/src/self_evolve/scripts/retire_rule.py`

- [ ] **Step 1: 实现 retire_rule.py**

```python
#!/usr/bin/env python3
"""Retire a rule. Zero dependencies."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    agents_dir = script_dir.parent.parent.parent
    return agents_dir / "self-evolve" / "rules"


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: retire_rule.py <rule-id>", file=sys.stderr)
        sys.exit(1)

    rule_id = sys.argv[1]
    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    path = rules_dir / f"{rule_id}.json"
    if not path.exists():
        print(f"Rule not found: {rule_id}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "retired"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Retired rule: {rule_id}")


if __name__ == "__main__":
    main()
```

---

### Task 8: 创建 list_rules.py 脚本

**Files:**
- Create: `packages/self-evolve/src/self_evolve/scripts/list_rules.py`

- [ ] **Step 1: 实现 list_rules.py**

与 `find_rules.py` 的区别：直接从 `rules/` 目录读取 JSON 文件（不依赖 `catalog.json`，不需要先 `sync`）。

```python
#!/usr/bin/env python3
"""List rules directly from the rules directory. Zero dependencies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _resolve_rules_dir(script_dir: Path) -> Path:
    agents_dir = script_dir.parent.parent.parent
    return agents_dir / "self-evolve" / "rules"


def _load_all_rules(rules_dir: Path) -> list[dict]:
    if not rules_dir.exists():
        return []
    rules = []
    for path in sorted(rules_dir.glob("R-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rules.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return rules


def _filter_rules(
    rules: list[dict],
    *,
    status: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    results = []
    for rule in rules:
        if status and rule.get("status") != status:
            continue
        if domain and rule.get("domain") != domain:
            continue
        if tag and tag not in rule.get("tags", []):
            continue
        if keyword:
            needle = keyword.lower()
            haystack = " ".join([
                str(rule.get("title", "")),
                str(rule.get("statement", "")),
                str(rule.get("rationale", "")),
            ]).lower()
            if needle not in haystack:
                continue
        results.append(rule)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="List self-evolve rules from the rules directory.")
    parser.add_argument("--status")
    parser.add_argument("--domain")
    parser.add_argument("--tag")
    parser.add_argument("--keyword")
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()

    rules_dir = _resolve_rules_dir(Path(__file__).resolve().parent)
    all_rules = _load_all_rules(rules_dir)

    if not args.status and not args.domain and not args.tag and not args.keyword:
        args.status = "active"

    filtered = _filter_rules(all_rules, status=args.status, domain=args.domain, tag=args.tag, keyword=args.keyword)
    if not filtered:
        print("No matching rules.")
        return

    for rule in filtered:
        print(f"[{rule.get('status')}] {rule.get('id')}: {rule.get('title')}")
        if args.detail:
            print(f"  Statement: {rule.get('statement', '')}")
            print(f"  Rationale: {rule.get('rationale', '')}")
            print(f"  Domain: {rule.get('domain', '')}")
            print(f"  Tags: {', '.join(rule.get('tags', [])) or 'none'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交 Chunk 1**

```bash
git add -A packages/self-evolve/src/self_evolve/
git commit -m "refactor(self-evolve): 精简模型层，移除 Session/Candidate，新增独立 Rule 操作脚本"
```

---

## Chunk 2: CLI 精简与 Sync 改造

### Task 9: 精简 CLI

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/plugin_cli.py`

- [ ] **Step 1: 删除所有子命令组**

从 `plugin_cli.py` 中移除：
- `session_app` 及 `session_record_command`
- `detect_app` 及 `detect_run_command`
- `candidate_app` 及所有子命令（list/show/accept/reject/edit）
- `rule_app` 及所有子命令（add/list/show/edit/retire）

删除对应的 import：`from self_evolve.candidate_ops import ...`、`from self_evolve.detector import ...`、`from self_evolve.rule_ops import ...`、`from self_evolve.session_ops import record_session`、`from self_evolve.storage import load_candidate, load_rule`

保留的 import：`from self_evolve.session_ops import initialize_project` → 改为 `from self_evolve.config import ...` 内联初始化逻辑（因为 `session_ops.py` 已删除）。

- [ ] **Step 2: 重写 init 命令**

`init` 不再调用 `initialize_project()`（该函数已随 `session_ops.py` 删除），改为直接内联：

```python
@app.command("init", help=_t(language, "init.help"))
def init_command() -> None:
    runtime = runtime_factory()
    try:
        project_root = runtime.cwd
        existing_root = find_project_root(project_root)
        if existing_root is not None and load_config(existing_root) is not None:
            typer.echo(_tr(runtime, "warning.already_initialized", path=str(existing_root)))
            return
        template_language = _prompt_template_language(runtime)
        ensure_no_legacy_layout(project_root)
        rules_dir(project_root).mkdir(parents=True, exist_ok=True)
        save_config(project_root, SelfEvolveConfig(language=template_language))
        sync_skill(project_root)
        typer.echo(_tr(runtime, "init.completed"))
    except LegacyLayoutError:
        _raise_legacy_error(runtime)
```

- [ ] **Step 3: 简化 status 命令**

`status` 调用简化后的 `get_status()`，只显示 rules 统计。

- [ ] **Step 4: 保留 sync 命令不变**（sync 的改造在 Task 12）

- [ ] **Step 5: 删除辅助函数**

移除 `_print_candidate()`、`_print_rule()` 函数（不再需要）。

---

### Task 10: 精简 status_ops.py

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/status_ops.py`

- [ ] **Step 1: 只统计 rules**

```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from self_evolve.storage import list_rules


@dataclass(slots=True, frozen=True)
class SelfEvolveStatus:
    rule_counts: dict[str, int]


def get_status(project_root: Path) -> SelfEvolveStatus:
    rules = list_rules(project_root)
    return SelfEvolveStatus(
        rule_counts=dict(Counter(rule.status for rule in rules)),
    )
```

- [ ] **Step 2: 更新 CLI 中 status 命令的输出**

`plugin_cli.py` 中 `status_command` 只输出 rules 统计行，移除 sessions 和 candidates 输出。

---

### Task 11: 精简 messages.py

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/messages.py`

- [ ] **Step 1: 删除废弃的翻译条目**

从 `en` 和 `zh-CN` 两个字典中移除以下 key：
- `session.app.help`, `session.record.help`
- `detect.app.help`, `detect.run.help`
- `candidate.app.help`, `candidate.list.help`, `candidate.show.help`, `candidate.accept.help`, `candidate.reject.help`, `candidate.edit.help`
- `rule.app.help`, `rule.add.help`, `rule.list.help`, `rule.show.help`, `rule.edit.help`, `rule.retire.help`
- `saved.session`, `saved.candidate`, `saved.rule`
- `updated.candidate`, `updated.rule`, `retired.rule`, `rejected.candidate`
- `detect.completed`
- `status.sessions`, `status.candidates`
- `list.empty`

保留：`app.help`, `metadata.help`, `init.help`, `init.language.prompt`, `sync.help`, `status.help`, `status.rules`, `warning.*`, `init.completed`, `sync.completed`, `legacy.error`

- [ ] **Step 2: 更新 status 翻译格式**

将 `status.rules` 的格式从 `"Rules: {counts}"` 改为同时包含 total：

```python
"status.rules": "Rules: total={total}, {counts}",
# zh-CN:
"status.rules": "规则：总数={total}，{counts}",
```

---

### Task 12: 改造 sync.py

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/sync.py`

- [ ] **Step 1: 更新 _sync_script → _sync_scripts**

```python
def _sync_scripts(output_dir: Path) -> list[Path]:
    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for source in sorted(_SCRIPTS_DIR.glob("*.py")):
        destination = scripts_dir / source.name
        shutil.copy2(source, destination)
        paths.append(destination)
    return paths
```

- [ ] **Step 2: 更新 SyncResult**

将 `script_path: Path | None` 改为 `script_paths: list[Path]`。

- [ ] **Step 3: 更新 sync_skill 调用**

```python
script_paths = _sync_scripts(output_dir)
return SyncResult(
    path=skill_path,
    rules_count=len(rules),
    strategy=strategy,
    domain_files=domain_files,
    catalog_path=catalog_path,
    script_paths=script_paths,
)
```

- [ ] **Step 4: 简化 catalog.json**

从 `_render_catalog` 中移除 `source_sessions` 和 `source_candidates` 字段，catalog version 升为 3：

```python
payload = {
    "version": 3,
    ...
    "rules": [
        {
            "id": rule.id,
            "title": rule.title,
            "statement": rule.statement,
            "rationale": rule.rationale,
            "domain": rule.domain,
            "tags": list(rule.tags),
            "created_at": rule.created_at,
            "revision_of": rule.revision_of,
        }
        for rule in rules
    ],
}
```

- [ ] **Step 5: 更新 _SYNC_COPY 文案**

将 description 中涉及 session/candidate 的文案改为引导使用脚本：

```python
"en": {
    "description.with_rules": "When you work in this project, follow these approved rules. Use the reflection workflow below to add new rules when you learn something reusable.",
    "description.empty": "When you work in this project, no approved rules exist yet. Use the reflection workflow below to start building the rule set.",
    "no_active_rules": "> No active rules yet. Use the reflection workflow to add rules, then run `agent-kit self-evolve sync`.",
    ...
},
"zh-CN": {
    "description.with_rules": "当你在此项目中工作时，请优先遵循这些已批准的项目规则。如果学到可复用经验，请使用下方的反思注入流程新增规则。",
    "description.empty": "当你在此项目中工作时，当前还没有已批准规则。请使用下方的反思注入流程开始沉淀规则集。",
    "no_active_rules": "> 当前还没有 active 规则。请使用反思注入流程新增规则，然后运行 `agent-kit self-evolve sync`。",
    ...
},
```

- [ ] **Step 6: 移除 domain 详情中的 source_sessions/source_candidates**

`_render_domain_files` 中删除对 `rule.source_session_ids`、`rule.source_candidate_ids` 的引用。同时从 `_SYNC_COPY` 中删除 `domain.source_sessions`、`domain.source_candidates` 的 key。

- [ ] **Step 7: 确认 fingerprints.py 是否仍被引用**

如果 `sync.py` 不再 import `fingerprints`，则也删除 `fingerprints.py`（该逻辑已内联到 `add_rule.py` 脚本中）。

- [ ] **Step 8: 提交 Chunk 2**

```bash
git add -A packages/self-evolve/
git commit -m "refactor(self-evolve): CLI 精简至 init/sync/status，sync 改造为复制所有脚本"
```

---

## Chunk 3: Skill 模板重设计

### Task 13: 重写 Skill 主模板（中文版）

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/templates/skill_main.zh-CN.md.tpl`

- [ ] **Step 1: 重写模板**

```markdown
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
- **title**：简短标题（10 字以内）
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
```

---

### Task 14: 重写 Skill 主模板（英文版）

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/templates/skill_main.en.md.tpl`

- [ ] **Step 1: 重写为英文版**

内容与中文版对称，将所有文案翻译为英文。关键段落标题：
- `# Project Knowledge Rules`
- `## Reflection & Rule Injection`
- `### 1. Check existing rules`
- `### 2. Analyze and extract`
- `### 3. Write the rule`
- `### 4. Remind user to review`
- `## Rule Management`

---

### Task 15: 更新 find_rules.py（适配 catalog v3）

**Files:**
- Modify: `packages/self-evolve/src/self_evolve/scripts/find_rules.py`

- [ ] **Step 1: 移除 source_sessions/source_candidates 的输出**

在 `print_rules` 函数中，`--detail` 模式下不再打印 `Source sessions` 和 `Source candidates`。

- [ ] **Step 2: 提交 Chunk 3**

```bash
git add -A packages/self-evolve/src/self_evolve/templates/ packages/self-evolve/src/self_evolve/scripts/
git commit -m "feat(self-evolve): Skill 模板增加反思注入指令，适配 catalog v3"
```

---

## Chunk 4: 测试更新

### Task 16: 删除废弃测试

**Files:**
- Delete: `packages/self-evolve/tests/test_cli_session.py`
- Delete: `packages/self-evolve/tests/test_detector.py`

- [ ] **Step 1: 删除这两个测试文件**

---

### Task 17: 重写 CLI 测试

**Files:**
- Delete: `packages/self-evolve/tests/test_cli_candidate_rule.py`
- Create: `packages/self-evolve/tests/test_cli.py`

- [ ] **Step 1: 创建 test_cli.py**

沿用 `build_app(tmp_path)` 模式（使用 `SimpleNamespace` 构造 runtime + `CliRunner`）。

测试用例：
1. `test_init_creates_v5_layout` — 验证 `init` 创建 `rules/` 目录，不创建 `sessions/`、`candidates/`、`indexes/`
2. `test_init_uses_agent_kit_lang_as_default` — 验证模板语言默认值
3. `test_init_rejects_legacy_layout` — 验证检测到旧布局时报错（包括 `sessions/` 目录）
4. `test_init_idempotent` — 验证重复 init 不覆盖
5. `test_sync_outputs_skill_md` — 验证 sync 生成 SKILL.md
6. `test_status_shows_rule_counts` — 验证 status 输出
7. `test_help_switches_with_language` — 验证中英文 help

```python
def test_init_creates_v5_layout(tmp_path: Path):
    app = build_app(tmp_path)
    result = runner.invoke(app, ["init"], input="en\n")
    assert result.exit_code == 0
    assert (tmp_path / ".agents" / "self-evolve" / "rules").exists()
    assert not (tmp_path / ".agents" / "self-evolve" / "sessions").exists()
    assert not (tmp_path / ".agents" / "self-evolve" / "candidates").exists()
    assert not (tmp_path / ".agents" / "self-evolve" / "indexes").exists()
    assert (tmp_path / ".agents" / "skills" / "self-evolve" / "SKILL.md").exists()
```

---

### Task 18: 精简 test_models.py

**Files:**
- Modify: `packages/self-evolve/tests/test_models.py`

- [ ] **Step 1: 删除 Session/Candidate/Index 测试**

移除 `test_session_record_round_trip`、`test_candidate_round_trip`、`test_index_round_trip`。

保留 `test_rule_round_trip`（更新以匹配去掉 `source_session_ids`/`source_candidate_ids` 后的结构）。

移除 `test_id_generators_increment` 中对 `generate_session_id` 和 `generate_candidate_id` 的测试（这些函数已删除）。如果 `generate_rule_id` 也已删除（迁移到脚本），则整个测试函数也删除。

---

### Task 19: 精简 test_storage.py

**Files:**
- Modify: `packages/self-evolve/tests/test_storage.py`

- [ ] **Step 1: 删除 session/candidate/index 存储测试**

移除 `test_save_and_load_session`、`test_save_and_load_candidate`、`test_save_and_load_index`。

保留 `test_save_and_load_rule`（更新以匹配 v5 KnowledgeRule）。

---

### Task 20: 新增脚本测试

**Files:**
- Create: `packages/self-evolve/tests/test_scripts.py`

- [ ] **Step 1: 创建 test_scripts.py**

使用 `subprocess.run` 调用脚本（模拟真实使用场景），设置前先在 `tmp_path` 下创建 `.agents/skills/self-evolve/scripts/` 目录并复制脚本。

测试用例：

```python
import json
import subprocess
import sys
from pathlib import Path


def _setup_scripts(tmp_path: Path) -> Path:
    """将脚本复制到 tmp_path 下模拟项目结构"""
    scripts_dir = tmp_path / ".agents" / "skills" / "self-evolve" / "scripts"
    scripts_dir.mkdir(parents=True)
    src_scripts = Path(__file__).resolve().parent.parent / "src" / "self_evolve" / "scripts"
    for f in src_scripts.glob("*.py"):
        (scripts_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    return scripts_dir


def test_add_rule_creates_json_file(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "Test rule",
         "--statement", "Always test before commit.",
         "--rationale", "Prevents regressions.",
         "--domain", "testing",
         "--tag", "ci"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "R-001" in result.stdout
    rule_file = tmp_path / ".agents" / "self-evolve" / "rules" / "R-001.json"
    assert rule_file.exists()
    data = json.loads(rule_file.read_text(encoding="utf-8"))
    assert data["title"] == "Test rule"
    assert data["status"] == "active"


def test_add_rule_warns_on_duplicate(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    # 先添加一条
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "Always test.", "--rationale", "R", "--domain", "testing"],
        capture_output=True, text=True,
    )
    # 再添加同样的
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T2", "--statement", "Always test.", "--rationale", "R2", "--domain", "testing"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Warning" in result.stderr  # 警告但不阻止


def test_retire_rule(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "retire_rule.py"), "R-001"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(
        (tmp_path / ".agents" / "self-evolve" / "rules" / "R-001.json").read_text(encoding="utf-8")
    )
    assert data["status"] == "retired"


def test_edit_rule(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "Old", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "edit_rule.py"), "R-001", "--title", "New"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(
        (tmp_path / ".agents" / "self-evolve" / "rules" / "R-001.json").read_text(encoding="utf-8")
    )
    assert data["title"] == "New"


def test_list_rules(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "Test rule", "--statement", "S", "--rationale", "R", "--domain", "testing"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "list_rules.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "R-001" in result.stdout
```

---

### Task 21: 更新 test_sync.py

**Files:**
- Modify: `packages/self-evolve/tests/test_sync.py`

- [ ] **Step 1: 更新 KnowledgeRule 构造**

移除所有 `source_session_ids=...` 和 `source_candidate_ids=...` 参数。

- [ ] **Step 2: 更新 catalog 断言**

`catalog["version"]` 从 `2` 改为 `3`。移除 `assert catalog["rules"][0]["source_candidates"] == ["C-001"]`。

- [ ] **Step 3: 更新 config_version**

`test_sync_falls_back_to_agent_kit_lang_when_project_language_missing` 中 `config_version` 从 4 改为 5。

- [ ] **Step 4: 验证所有脚本被复制**

修改 `test_find_rules_script_reads_catalog_v2` → `test_scripts_are_synced_and_find_rules_works`：

```python
def test_scripts_are_synced_and_find_rules_works(tmp_path: Path):
    ...
    result = sync_skill(tmp_path)

    scripts = list((tmp_path / ".agents" / "skills" / "self-evolve" / "scripts").glob("*.py"))
    script_names = {s.name for s in scripts}
    assert "find_rules.py" in script_names
    assert "add_rule.py" in script_names
    assert "edit_rule.py" in script_names
    assert "retire_rule.py" in script_names
    assert "list_rules.py" in script_names
```

---

### Task 22: 更新 test_config.py

**Files:**
- Modify: `packages/self-evolve/tests/test_config.py`

- [ ] **Step 1: 更新 SelfEvolveConfig 构造**

移除 `auto_accept_enabled` 和 `auto_accept_min_confidence` 参数。

- [ ] **Step 2: 更新路径断言**

删除对 `sessions_dir`、`candidates_dir`、`indexes_dir` 的断言。

- [ ] **Step 3: 新增 v5 旧布局检测**

```python
def test_sessions_directory_treated_as_legacy(tmp_path: Path):
    (tmp_path / ".agents" / "self-evolve" / "sessions").mkdir(parents=True)
    with pytest.raises(LegacyLayoutError):
        ensure_no_legacy_layout(tmp_path)
```

- [ ] **Step 4: 运行全部测试**

Run: `uv run pytest packages/self-evolve/tests -q`
Expected: 所有测试通过

- [ ] **Step 5: 提交 Chunk 4**

```bash
git add -A packages/self-evolve/tests/
git commit -m "test(self-evolve): v5 测试重写——删除 Session/Candidate 测试，新增脚本层测试"
```

---

## Chunk 5: 文档与版本

### Task 23: 更新 pyproject.toml

**Files:**
- Modify: `packages/self-evolve/pyproject.toml`

- [ ] **Step 1: 版本号升级**

```toml
version = "0.5.0"
```

`force-include` 已包含 `scripts` 目录，无需额外修改。

---

### Task 24: 更新 AGENTS.md

**Files:**
- Modify: `packages/self-evolve/AGENTS.md`

- [ ] **Step 1: 重写命令列表**

只保留 `init`、`sync`、`status`。

- [ ] **Step 2: 更新核心概念**

移除 Session、Candidate、Detect 相关描述。核心概念只保留 Rule 和 Skill Sync。新增"脚本层"说明。

- [ ] **Step 3: 更新配置字段**

移除 `auto_accept_enabled`、`auto_accept_min_confidence`。`config_version` 改为 5。

- [ ] **Step 4: 更新数据存储**

只保留 `rules/` 目录，移除 `sessions/`、`candidates/`、`indexes/`。

- [ ] **Step 5: 更新旧格式标记**

说明 `sessions/` 和 `candidates/` 目录也被视为旧布局。

- [ ] **Step 6: 更新验证要点**

改为验证脚本层、Skill 模板反思指令、sync 输出。

---

### Task 25: 重写 README.md

**Files:**
- Modify: `packages/self-evolve/README.md`

- [ ] **Step 1: 重写为 v5 架构**

反映新的 `Agent → 脚本 → Rule → sync → SKILL.md` 流程。核心模型只有 Rule。命令只有 init/sync/status。脚本层作为 Agent 接口。

---

### Task 26: 重写 USAGE.md

**Files:**
- Modify: `packages/self-evolve/USAGE.md`

- [ ] **Step 1: 重写为 v5 使用指南**

重点放在：
1. 初始化项目
2. 通过 Skill 触发反思注入
3. 直接使用脚本管理规则
4. 同步到 Skill 输出
5. 通过 Git diff 审核

---

### Task 27: 归档详细说明

**Files:**
- Modify: `packages/self-evolve/docs/详细说明.md`

- [ ] **Step 1: 在文件头标记归档**

```markdown
> ⚠️ 本文档描述的是 v4 架构，已被 v5 取代。仅供参考。v5 使用指南见 `USAGE.md`。
```

---

### Task 28: 最终验证与提交

- [ ] **Step 1: 运行全部测试**

Run: `uv run pytest packages/self-evolve/tests -q`
Expected: 所有测试通过

- [ ] **Step 2: 提交文档**

```bash
git add -A packages/self-evolve/
git commit -m "docs(self-evolve): v5 文档更新——README/USAGE/AGENTS.md 反映新架构"
```

- [ ] **Step 3: 版本号提交**

```bash
git add packages/self-evolve/pyproject.toml packages/self-evolve/src/self_evolve/__init__.py
git commit -m "chore(self-evolve): 版本号升级至 0.5.0"
```
