# self-evolve v5: Skill 驱动的极简知识流水线 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 彻底重写 self-evolve 插件——从三层流水线（Session → Candidate → Rule）彻底转变为 Agent 直接操作 Rule 的极简架构。所有源码模块从零开始编写，不对任何旧版本（v1–v4）进行兼容、检测或迁移。

**Architecture:** v5 只有一个核心实体 Rule。CLI 仅提供 `init`/`sync`/`status` 三个基础设施命令。Rule CRUD 由 `scripts/` 目录下的零依赖 Python 脚本完成（纯 stdlib），`sync` 时自动复制到项目 `.agents/skills/self-evolve/scripts/`。Skill 模板包含反思注入指令，引导 Agent 从对话上下文中提取结构化知识并调用脚本写入规则。人工审核通过 Git diff 完成。

**Tech Stack:** Python 3.11+, Typer (仅 CLI 层), argparse (脚本层), pytest, hatchling

**不兼容声明:** v5 是完全重写。代码中不包含任何旧版本检测（无 `_LEGACY_MARKERS`）、无 `LegacyLayoutError`、无 `ensure_no_legacy_layout`、无旧配置版本迁移。如果项目中存在旧版本数据（如 `sessions/`、`candidates/`、`learnings/` 等目录），v5 不感知也不处理，用户须自行清理后重新 `init`。

---

## v5 目标源码结构

完成后 `src/self_evolve/` 的文件清单（全部从零编写或保留原有工具模块）：

```text
src/self_evolve/
├── __init__.py          # 版本常量
├── config.py            # 配置管理（无旧版检测）
├── models.py            # 仅 KnowledgeRule
├── storage.py           # 仅 Rule 持久化
├── sync.py              # Skill 生成引擎
├── plugin_cli.py        # CLI（仅 init/sync/status）
├── messages.py          # i18n 翻译
├── status_ops.py        # 状态统计
├── locale.py            # 语言决议（v4 工具模块，保留不变）
├── jsonc.py             # JSONC 解析器（v4 工具模块，保留不变）
├── scripts/
│   ├── add_rule.py      # 新增规则
│   ├── edit_rule.py     # 编辑规则
│   ├── retire_rule.py   # 停用规则
│   ├── list_rules.py    # 列出规则（读 rules/ 目录）
│   └── find_rules.py    # 检索规则（读 catalog.json）
└── templates/
    ├── skill_main.en.md.tpl
    ├── skill_main.zh-CN.md.tpl
    ├── skill_inline.en.md.tpl
    ├── skill_inline.zh-CN.md.tpl
    ├── skill_index.en.md.tpl
    ├── skill_index.zh-CN.md.tpl
    ├── domain_detail.en.md.tpl
    └── domain_detail.zh-CN.md.tpl
```

v4 中删除、不在 v5 中出现的模块：`session_ops.py`、`candidate_ops.py`、`detector.py`、`index_ops.py`、`rule_ops.py`、`ids.py`、`fingerprints.py`

---

## Chunk 1: 清空 v4 业务代码，建立 v5 骨架

### Task 1: 删除所有 v4 业务模块

**Files:**
- Delete: `packages/self-evolve/src/self_evolve/session_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/candidate_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/detector.py`
- Delete: `packages/self-evolve/src/self_evolve/index_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/rule_ops.py`
- Delete: `packages/self-evolve/src/self_evolve/ids.py`
- Delete: `packages/self-evolve/src/self_evolve/fingerprints.py`

- [ ] **Step 1: 删除以上 7 个文件**

这些模块包含 v4 的 Session/Candidate 流水线逻辑。v5 不在这些模块基础上修改，而是从零编写替代模块。

### Task 2: 删除所有 v4 测试

**Files:**
- Delete: `packages/self-evolve/tests/test_cli_session.py`
- Delete: `packages/self-evolve/tests/test_cli_candidate_rule.py`
- Delete: `packages/self-evolve/tests/test_detector.py`
- Delete: `packages/self-evolve/tests/test_models.py`
- Delete: `packages/self-evolve/tests/test_storage.py`
- Delete: `packages/self-evolve/tests/test_config.py`
- Delete: `packages/self-evolve/tests/test_sync.py`

- [ ] **Step 1: 删除以上 7 个测试文件**

v5 测试将在 Chunk 6 中全部从零编写，不在 v4 测试基础上增删。

### Task 3: 更新版本常量

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/__init__.py`

- [ ] **Step 1: 写入 v5 版本常量**

```python
"""Self-evolve toolkit package."""

__all__ = ["API_VERSION", "CONFIG_VERSION", "PLUGIN_ID", "__version__"]

__version__ = "0.5.0"
PLUGIN_ID = "self-evolve"
API_VERSION = 1
CONFIG_VERSION = 5
```

- [ ] **Step 2: 验证**

Run: `cd packages/self-evolve && python -c "from self_evolve import CONFIG_VERSION; assert CONFIG_VERSION == 5; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交 Chunk 1**

```bash
git add -A packages/self-evolve/
git commit -m "refactor(self-evolve): 清空 v4 业务模块和测试，升级至 v5 骨架"
```

---

## Chunk 2: 核心数据层

### Task 4: 从零编写 models.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/models.py`

- [ ] **Step 1: 编写 KnowledgeRule**

v5 只有一个数据模型。没有 `SessionRecord`、`KnowledgeCandidate`、`KnowledgeIndex`。

```python
"""v5 数据模型——仅 KnowledgeRule。"""

from __future__ import annotations

from dataclasses import dataclass, field


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

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "status": self.status,
            "title": self.title,
            "statement": self.statement,
            "rationale": self.rationale,
            "domain": self.domain,
            "tags": list(self.tags),
            "revision_of": self.revision_of,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> KnowledgeRule:
        return cls(
            id=str(data["id"]),
            created_at=str(data["created_at"]),
            status=str(data["status"]),
            title=str(data["title"]),
            statement=str(data["statement"]),
            rationale=str(data["rationale"]),
            domain=str(data["domain"]),
            tags=[str(t) for t in data.get("tags", [])],  # type: ignore[union-attr]
            revision_of=str(data.get("revision_of", "")),
        )
```

---

### Task 5: 从零编写 config.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/config.py`

- [ ] **Step 1: 编写完整配置模块**

与 v4 的关键区别：
- 无 `_LEGACY_MARKERS` 常量
- 无 `LegacyLayoutError` 异常
- 无 `ensure_no_legacy_layout()` 函数
- 无 `sessions_dir()`、`candidates_dir()`、`indexes_dir()` 路径函数
- `SelfEvolveConfig` 无 `auto_accept_enabled`、`auto_accept_min_confidence` 字段
- `load_config` 仅校验 `config_version == 5`，不识别或处理旧版本

```python
"""v5 配置管理。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from self_evolve import CONFIG_VERSION, PLUGIN_ID
from self_evolve.jsonc import loads as jsonc_loads

_EVOLVE_DIR = ".agents/self-evolve"
_SKILL_DIR = ".agents/skills/self-evolve"


@dataclass(slots=True, frozen=True)
class SelfEvolveConfig:
    language: str | None = None
    inline_threshold: int = 20


def evolve_dir(project_root: Path) -> Path:
    return project_root / _EVOLVE_DIR


def config_file_path(project_root: Path) -> Path:
    return evolve_dir(project_root) / "config.jsonc"


def rules_dir(project_root: Path) -> Path:
    return evolve_dir(project_root) / "rules"


def skill_dir(project_root: Path) -> Path:
    return project_root / _SKILL_DIR


def find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / _EVOLVE_DIR).is_dir() or (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def save_config(project_root: Path, config: SelfEvolveConfig) -> Path:
    path = config_file_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    payload = {
        "plugin_id": PLUGIN_ID,
        "config_version": CONFIG_VERSION,
        "language": config.language,
        "inline_threshold": config.inline_threshold,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_config(project_root: Path) -> SelfEvolveConfig | None:
    path = config_file_path(project_root)
    if not path.exists():
        return None
    raw = jsonc_loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    if raw.get("config_version") != CONFIG_VERSION:
        return None
    return SelfEvolveConfig(
        language=raw.get("language"),
        inline_threshold=int(raw.get("inline_threshold", 20)),
    )


def resolve_template_language(project_root: Path) -> str:
    cfg = load_config(project_root)
    if cfg and cfg.language:
        return cfg.language
    env_lang = os.environ.get("AGENT_KIT_LANG", "")
    if env_lang:
        return env_lang
    return "en"
```

---

### Task 6: 从零编写 storage.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/storage.py`

- [ ] **Step 1: 编写 Rule 持久化**

只有三个公开函数：`save_rule`、`load_rule`、`list_rules`。无 session/candidate/index 相关函数。

```python
"""v5 存储层——仅 Rule 持久化。"""

from __future__ import annotations

import json
from pathlib import Path

from self_evolve.config import rules_dir
from self_evolve.models import KnowledgeRule


def save_rule(project_root: Path, rule: KnowledgeRule) -> Path:
    directory = rules_dir(project_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{rule.id}.json"
    path.write_text(
        json.dumps(rule.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_rule(project_root: Path, rule_id: str) -> KnowledgeRule | None:
    path = rules_dir(project_root) / f"{rule_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return KnowledgeRule.from_dict(data)
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def list_rules(project_root: Path) -> list[KnowledgeRule]:
    directory = rules_dir(project_root)
    if not directory.exists():
        return []
    rules: list[KnowledgeRule] = []
    for path in sorted(directory.glob("R-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rules.append(KnowledgeRule.from_dict(data))
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return rules
```

- [ ] **Step 2: 验证数据层编译通过**

Run: `cd packages/self-evolve && python -c "from self_evolve.storage import save_rule, load_rule, list_rules; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交 Chunk 2**

```bash
git add -A packages/self-evolve/src/self_evolve/
git commit -m "feat(self-evolve): v5 核心数据层——KnowledgeRule + Config + Storage 从零编写"
```

---

## Chunk 3: 独立脚本层

### Task 7: 创建 add_rule.py 脚本

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

### Task 8: 创建 edit_rule.py 脚本

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

### Task 9: 创建 retire_rule.py 脚本

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

### Task 10: 创建 list_rules.py 脚本

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

---

### Task 11: 重写 find_rules.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/scripts/find_rules.py`

- [ ] **Step 1: 重写 find_rules.py 适配 v5 catalog**

v5 的 `catalog.json` 格式为 version 1（全新格式），规则条目中不包含 `source_sessions`、`source_candidates` 字段。

```python
#!/usr/bin/env python3
"""Search rules from the catalog.json generated by sync. Zero dependencies."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_catalog(script_dir: Path) -> dict | None:
    catalog_path = script_dir.parent / "catalog.json"
    if not catalog_path.exists():
        return None
    try:
        return json.loads(catalog_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def filter_rules(
    catalog: dict,
    *,
    domain: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    results = []
    for rule in catalog.get("rules", []):
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


def print_stats(catalog: dict) -> None:
    summary = catalog.get("summary", {})
    print(f"Total rules: {summary.get('total_rules', 0)}")
    for domain, count in sorted(summary.get("domains", {}).items()):
        print(f"  {domain}: {count}")


def print_rules(rules: list[dict], *, detail: bool = False) -> None:
    for rule in rules:
        print(f"[{rule.get('id')}] {rule.get('title')} ({rule.get('domain')})")
        if detail:
            print(f"  Statement: {rule.get('statement', '')}")
            print(f"  Rationale: {rule.get('rationale', '')}")
            print(f"  Tags: {', '.join(rule.get('tags', [])) or 'none'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search self-evolve rules from catalog.")
    parser.add_argument("--domain", help="Filter by domain")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument("--keyword", help="Search in title/statement/rationale")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--detail", action="store_true", help="Show full rule details")
    args = parser.parse_args()

    catalog = load_catalog(Path(__file__).resolve().parent)
    if catalog is None:
        print("No catalog.json found. Run 'agent-kit self-evolve sync' first.", file=sys.stderr)
        sys.exit(1)

    if args.stats or (not args.domain and not args.tag and not args.keyword):
        print_stats(catalog)
        return

    filtered = filter_rules(catalog, domain=args.domain, tag=args.tag, keyword=args.keyword)
    if not filtered:
        print("No matching rules.")
        return

    print_rules(filtered, detail=args.detail)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交 Chunk 3**

```bash
git add -A packages/self-evolve/src/self_evolve/
git commit -m "feat(self-evolve): v5 脚本层——add/edit/retire/list/find 五个零依赖脚本"
```

---

## Chunk 4: Sync 引擎与模板

### Task 12: 从零编写 sync.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/sync.py`

- [ ] **Step 1: 编写完整 sync 模块**

关键设计：
- `SyncResult.script_paths: list[Path]`（复数，复制所有脚本）
- catalog.json version = 1（全新格式，无旧版递增）
- catalog 规则条目不包含 `source_sessions`、`source_candidates`
- `_SYNC_COPY` 文案中不涉及 session/candidate

```python
"""v5 Skill 同步引擎。"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from string import Template

from self_evolve.config import resolve_template_language, rules_dir, skill_dir
from self_evolve.models import KnowledgeRule
from self_evolve.storage import list_rules

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_SCRIPTS_DIR = Path(__file__).parent / "scripts"

_SYNC_COPY: dict[str, dict[str, str]] = {
    "en": {
        "description.with_rules": "When you work in this project, follow these approved rules. Use the reflection workflow below to add new rules when you learn something reusable.",
        "description.empty": "When you work in this project, no approved rules exist yet. Use the reflection workflow below to start building the rule set.",
        "no_active_rules": "> No active rules yet. Use the reflection workflow to add rules, then run `agent-kit self-evolve sync`.",
        "domain.statement": "Statement",
        "domain.rationale": "Rationale",
        "domain.tags": "Tags",
        "none": "none",
    },
    "zh-CN": {
        "description.with_rules": "当你在此项目中工作时，请优先遵循这些已批准的项目规则。如果学到可复用经验，请使用下方的反思注入流程新增规则。",
        "description.empty": "当你在此项目中工作时，当前还没有已批准规则。请使用下方的反思注入流程开始沉淀规则集。",
        "no_active_rules": "> 当前还没有 active 规则。请使用反思注入流程新增规则，然后运行 `agent-kit self-evolve sync`。",
        "domain.statement": "规则描述",
        "domain.rationale": "原因",
        "domain.tags": "标签",
        "none": "无",
    },
}


@dataclass(slots=True, frozen=True)
class SyncResult:
    path: Path
    rules_count: int
    strategy: str = "inline"
    domain_files: list[Path] = field(default_factory=list)
    catalog_path: Path | None = None
    script_paths: list[Path] = field(default_factory=list)


def sync_skill(
    project_root: Path,
    *,
    inline_threshold: int = 20,
    language: str | None = None,
) -> SyncResult:
    lang = language or resolve_template_language(project_root)
    rules = [r for r in list_rules(project_root) if r.status == "active"]
    output_dir = skill_dir(project_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    strategy = "inline" if len(rules) <= inline_threshold else "index"

    skill_md = _render_skill_md(rules, strategy, lang)
    skill_path = output_dir / "SKILL.md"
    skill_path.write_text(skill_md, encoding="utf-8")

    catalog_path = _render_catalog(output_dir, rules)
    domain_files = _render_domain_files(output_dir, rules, lang) if strategy == "index" else []
    _cleanup_stale_domains(output_dir, rules, strategy)
    script_paths = _sync_scripts(output_dir)

    return SyncResult(
        path=skill_path,
        rules_count=len(rules),
        strategy=strategy,
        domain_files=domain_files,
        catalog_path=catalog_path,
        script_paths=script_paths,
    )


def _copy(language: str, key: str) -> str:
    lang_dict = _SYNC_COPY.get(language, _SYNC_COPY["en"])
    return lang_dict.get(key, _SYNC_COPY["en"].get(key, key))


def _load_template(name: str, language: str) -> Template:
    lang_path = _TEMPLATES_DIR / f"{name}.{language}.md.tpl"
    if lang_path.exists():
        return Template(lang_path.read_text(encoding="utf-8"))
    fallback = _TEMPLATES_DIR / f"{name}.en.md.tpl"
    return Template(fallback.read_text(encoding="utf-8"))


def _group_by_domain(rules: list[KnowledgeRule]) -> dict[str, list[KnowledgeRule]]:
    groups: dict[str, list[KnowledgeRule]] = defaultdict(list)
    for rule in rules:
        groups[rule.domain].append(rule)
    return dict(groups)


def _render_skill_md(rules: list[KnowledgeRule], strategy: str, language: str) -> str:
    description = _copy(language, "description.with_rules" if rules else "description.empty")
    if strategy == "inline":
        rules_section = _render_inline_section(rules, language)
    else:
        rules_section = _render_index_section(rules, language)
    tpl = _load_template("skill_main", language)
    return tpl.safe_substitute(
        description=description,
        rules_section=rules_section,
        last_synced=str(date.today()),
    )


def _render_inline_section(rules: list[KnowledgeRule], language: str) -> str:
    if not rules:
        return _copy(language, "no_active_rules")
    groups = _group_by_domain(rules)
    tpl = _load_template("skill_inline", language)
    parts: list[str] = []
    for domain in sorted(groups):
        lines = [f"### {domain}\n"]
        for rule in groups[domain]:
            lines.append(f"**{rule.id}: {rule.title}**\n")
            lines.append(f"- {_copy(language, 'domain.statement')}: {rule.statement}")
            lines.append(f"- {_copy(language, 'domain.rationale')}: {rule.rationale}")
            tags_str = ", ".join(rule.tags) if rule.tags else _copy(language, "none")
            lines.append(f"- {_copy(language, 'domain.tags')}: {tags_str}\n")
        parts.append("\n".join(lines))
    return tpl.safe_substitute(domain_groups="\n".join(parts))


def _render_index_section(rules: list[KnowledgeRule], language: str) -> str:
    groups = _group_by_domain(rules)
    tpl = _load_template("skill_index", language)
    rows: list[str] = []
    for domain in sorted(groups):
        count = len(groups[domain])
        latest = max(r.created_at for r in groups[domain])
        rows.append(f"| {domain} | {count} | {latest[:10]} | [→ details](domains/{domain}.md) |")
    return tpl.safe_substitute(domain_table_rows="\n".join(rows))


def _render_catalog(output_dir: Path, rules: list[KnowledgeRule]) -> Path:
    domains: dict[str, int] = defaultdict(int)
    for rule in rules:
        domains[rule.domain] += 1
    payload = {
        "version": 1,
        "last_synced": str(date.today()),
        "summary": {
            "total_rules": len(rules),
            "domains": dict(sorted(domains.items())),
        },
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
    path = output_dir / "catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _render_domain_files(
    output_dir: Path, rules: list[KnowledgeRule], language: str
) -> list[Path]:
    groups = _group_by_domain(rules)
    domains_dir = output_dir / "domains"
    domains_dir.mkdir(parents=True, exist_ok=True)
    tpl = _load_template("domain_detail", language)
    paths: list[Path] = []
    for domain in sorted(groups):
        lines: list[str] = []
        for rule in groups[domain]:
            lines.append(f"**{rule.id}: {rule.title}**\n")
            lines.append(f"- {_copy(language, 'domain.statement')}: {rule.statement}")
            lines.append(f"- {_copy(language, 'domain.rationale')}: {rule.rationale}")
            tags_str = ", ".join(rule.tags) if rule.tags else _copy(language, "none")
            lines.append(f"- {_copy(language, 'domain.tags')}: {tags_str}\n")
        content = tpl.safe_substitute(domain=domain, rules_content="\n".join(lines))
        path = domains_dir / f"{domain}.md"
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def _cleanup_stale_domains(
    output_dir: Path, rules: list[KnowledgeRule], strategy: str
) -> None:
    domains_dir = output_dir / "domains"
    if not domains_dir.exists():
        return
    if strategy == "inline":
        shutil.rmtree(domains_dir)
        return
    active_domains = {r.domain for r in rules}
    for path in domains_dir.glob("*.md"):
        if path.stem not in active_domains:
            path.unlink()


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

---

### Task 13: 重写 Skill 主模板（中文版）

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/templates/skill_main.zh-CN.md.tpl`

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
- Rewrite: `packages/self-evolve/src/self_evolve/templates/skill_main.en.md.tpl`

- [ ] **Step 1: 重写为英文版**

内容与中文版对称，将所有文案翻译为英文。关键段落标题：
- `# Project Knowledge Rules`
- `## Reflection & Rule Injection`
- `### 1. Check existing rules`
- `### 2. Analyze and extract`
- `### 3. Write the rule`
- `### 4. Remind user to review`
- `## Rule Management`

- [ ] **Step 2: 提交 Chunk 4**

```bash
git add -A packages/self-evolve/src/self_evolve/
git commit -m "feat(self-evolve): v5 Sync 引擎与 Skill 模板从零编写，含反思注入指令"
```

---

## Chunk 5: CLI 层

### Task 15: 从零编写 messages.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/messages.py`

- [ ] **Step 1: 编写 v5 翻译字典**

只包含 v5 需要的翻译条目，不从 v4 字典中删减。

```python
"""v5 CLI 翻译。"""

from __future__ import annotations

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "app.help": "Self-evolve: project-level knowledge rule management.",
        "metadata.help": "Output plugin metadata as JSON.",
        "init.help": "Initialize self-evolve for this project.",
        "init.language.prompt": "Select template language (en / zh-CN)",
        "init.completed": "Initialized successfully.",
        "sync.help": "Sync active rules to the Skill output.",
        "sync.completed": "Sync completed: {rules_count} active rules, strategy={strategy}.",
        "status.help": "Show self-evolve status.",
        "status.rules": "Rules: total={total}, {counts}",
        "warning.not_initialized": "Project not initialized. Run 'agent-kit self-evolve init' first.",
        "warning.already_initialized": "Already initialized at {path}.",
        "warning.not_found": "{entity} not found: {id}",
    },
    "zh-CN": {
        "app.help": "Self-evolve：项目级知识规则管理。",
        "metadata.help": "以 JSON 格式输出插件元信息。",
        "init.help": "为当前项目初始化 self-evolve。",
        "init.language.prompt": "选择模板语言 (en / zh-CN)",
        "init.completed": "初始化完成。",
        "sync.help": "将 active 规则同步到 Skill 输出。",
        "sync.completed": "同步完成：{rules_count} 条 active 规则，策略={strategy}。",
        "status.help": "显示 self-evolve 状态。",
        "status.rules": "规则：总数={total}，{counts}",
        "warning.not_initialized": "项目未初始化。请先运行 'agent-kit self-evolve init'。",
        "warning.already_initialized": "已在 {path} 初始化过。",
        "warning.not_found": "未找到{entity}：{id}",
    },
}


def translate(language: str, key: str, **kwargs: object) -> str:
    lang_dict = _MESSAGES.get(language, _MESSAGES["en"])
    template = lang_dict.get(key, _MESSAGES["en"].get(key, key))
    if kwargs:
        return template.format(**kwargs)
    return template
```

---

### Task 16: 从零编写 status_ops.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/status_ops.py`

- [ ] **Step 1: 编写 v5 状态统计**

只统计 rules，无 session/candidate 统计。

```python
"""v5 状态统计。"""

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

---

### Task 17: 从零编写 plugin_cli.py

**Files:**
- Rewrite: `packages/self-evolve/src/self_evolve/plugin_cli.py`

- [ ] **Step 1: 编写 v5 CLI**

只包含 `init`、`sync`、`status` 三个命令和 `--plugin-metadata` 选项。不从 v4 的 CLI 中删减。

```python
"""v5 CLI——仅 init/sync/status。"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import typer

from self_evolve import API_VERSION, CONFIG_VERSION, PLUGIN_ID, __version__
from self_evolve.config import (
    SelfEvolveConfig,
    find_project_root,
    load_config,
    rules_dir,
    save_config,
)
from self_evolve.locale import resolve_language
from self_evolve.messages import translate
from self_evolve.status_ops import get_status
from self_evolve.sync import sync_skill


@dataclass(slots=True)
class PluginRuntime:
    logger: logging.Logger
    cwd: Path
    config_root: Path
    data_root: Path
    cache_root: Path


def _default_runtime() -> PluginRuntime:
    return PluginRuntime(
        logger=logging.getLogger(PLUGIN_ID),
        cwd=Path.cwd(),
        config_root=Path(os.environ.get("AGENT_KIT_CONFIG_DIR", Path.home() / ".config" / "agent-kit")),
        data_root=Path(os.environ.get("AGENT_KIT_DATA_DIR", Path.home() / ".local" / "share" / "agent-kit")),
        cache_root=Path(os.environ.get("AGENT_KIT_CACHE_DIR", Path.home() / ".cache" / "agent-kit")),
    )


def _t(language: str, key: str, **kwargs: object) -> str:
    return translate(language, key, **kwargs)


def _tr(runtime: PluginRuntime, key: str, **kwargs: object) -> str:
    lang = resolve_language(SimpleNamespace(config_root=runtime.config_root))
    return translate(lang, key, **kwargs)


def _prompt_template_language(runtime: PluginRuntime) -> str:
    env_lang = os.environ.get("AGENT_KIT_LANG", "")
    if env_lang in ("en", "zh-CN"):
        return env_lang
    prompt_text = _tr(runtime, "init.language.prompt")
    choice = typer.prompt(prompt_text, default="en")
    return choice if choice in ("en", "zh-CN") else "en"


def build_app(
    cwd: Path | None = None,
    runtime_factory: Callable[[], PluginRuntime] = _default_runtime,
) -> typer.Typer:
    language = resolve_language(
        SimpleNamespace(config_root=Path(os.environ.get(
            "AGENT_KIT_CONFIG_DIR",
            Path.home() / ".config" / "agent-kit",
        )))
    )

    app = typer.Typer(help=_t(language, "app.help"), no_args_is_help=True)

    @app.callback(invoke_without_command=True)
    def main_callback(
        plugin_metadata: bool = typer.Option(False, "--plugin-metadata", help=_t(language, "metadata.help")),
    ) -> None:
        if plugin_metadata:
            typer.echo(json.dumps({
                "plugin_id": PLUGIN_ID,
                "installed_version": __version__,
                "api_version": API_VERSION,
                "config_version": CONFIG_VERSION,
            }))
            raise typer.Exit()

    @app.command("init", help=_t(language, "init.help"))
    def init_command() -> None:
        runtime = runtime_factory()
        if cwd is not None:
            runtime.cwd = cwd
        project_root = runtime.cwd
        existing_root = find_project_root(project_root)
        if existing_root is not None and load_config(existing_root) is not None:
            typer.echo(_tr(runtime, "warning.already_initialized", path=str(existing_root)))
            return
        template_language = _prompt_template_language(runtime)
        rules_dir(project_root).mkdir(parents=True, exist_ok=True)
        save_config(project_root, SelfEvolveConfig(language=template_language))
        sync_skill(project_root)
        typer.echo(_tr(runtime, "init.completed"))

    @app.command("sync", help=_t(language, "sync.help"))
    def sync_command() -> None:
        runtime = runtime_factory()
        if cwd is not None:
            runtime.cwd = cwd
        project_root = runtime.cwd
        cfg = load_config(project_root)
        if cfg is None:
            typer.echo(_tr(runtime, "warning.not_initialized"), err=True)
            raise typer.Exit(1)
        result = sync_skill(project_root, inline_threshold=cfg.inline_threshold)
        typer.echo(_tr(
            runtime,
            "sync.completed",
            rules_count=result.rules_count,
            strategy=result.strategy,
        ))

    @app.command("status", help=_t(language, "status.help"))
    def status_command() -> None:
        runtime = runtime_factory()
        if cwd is not None:
            runtime.cwd = cwd
        project_root = runtime.cwd
        cfg = load_config(project_root)
        if cfg is None:
            typer.echo(_tr(runtime, "warning.not_initialized"), err=True)
            raise typer.Exit(1)
        status = get_status(project_root)
        total = sum(status.rule_counts.values())
        counts_str = ", ".join(f"{k}={v}" for k, v in sorted(status.rule_counts.items()))
        typer.echo(_tr(runtime, "status.rules", total=total, counts=counts_str or "0"))

    return app


def main() -> None:
    app = build_app()
    app()
```

- [ ] **Step 2: 验证 CLI 编译通过**

Run: `cd packages/self-evolve && python -c "from self_evolve.plugin_cli import build_app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交 Chunk 5**

```bash
git add -A packages/self-evolve/src/self_evolve/
git commit -m "feat(self-evolve): v5 CLI 层从零编写——init/sync/status + messages + status_ops"
```

---

## Chunk 6: 测试

所有测试从零编写，不在 v4 测试基础上增删。

### Task 18: 创建 test_models.py

**Files:**
- Create: `packages/self-evolve/tests/test_models.py`

- [ ] **Step 1: 编写 KnowledgeRule 测试**

```python
from self_evolve.models import KnowledgeRule


def test_rule_round_trip():
    rule = KnowledgeRule(
        id="R-001",
        created_at="2026-03-31T12:00:00Z",
        status="active",
        title="Test rule",
        statement="Always test before commit.",
        rationale="Prevents regressions.",
        domain="testing",
        tags=["ci", "quality"],
        revision_of="",
    )
    data = rule.to_dict()
    restored = KnowledgeRule.from_dict(data)
    assert restored.id == rule.id
    assert restored.title == rule.title
    assert restored.tags == rule.tags
    assert restored.revision_of == ""


def test_rule_from_dict_minimal():
    data = {
        "id": "R-002",
        "created_at": "2026-03-31T12:00:00Z",
        "status": "active",
        "title": "Minimal",
        "statement": "S",
        "rationale": "R",
        "domain": "d",
    }
    rule = KnowledgeRule.from_dict(data)
    assert rule.tags == []
    assert rule.revision_of == ""
```

---

### Task 19: 创建 test_config.py

**Files:**
- Create: `packages/self-evolve/tests/test_config.py`

- [ ] **Step 1: 编写配置测试**

```python
from pathlib import Path

from self_evolve.config import (
    SelfEvolveConfig,
    evolve_dir,
    find_project_root,
    load_config,
    rules_dir,
    save_config,
    skill_dir,
)


def test_path_helpers(tmp_path: Path):
    assert evolve_dir(tmp_path) == tmp_path / ".agents" / "self-evolve"
    assert rules_dir(tmp_path) == tmp_path / ".agents" / "self-evolve" / "rules"
    assert skill_dir(tmp_path) == tmp_path / ".agents" / "skills" / "self-evolve"


def test_save_and_load_config(tmp_path: Path):
    cfg = SelfEvolveConfig(language="zh-CN", inline_threshold=30)
    save_config(tmp_path, cfg)
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.language == "zh-CN"
    assert loaded.inline_threshold == 30


def test_load_config_returns_none_when_missing(tmp_path: Path):
    assert load_config(tmp_path) is None


def test_load_config_returns_none_for_wrong_version(tmp_path: Path):
    import json
    config_dir = tmp_path / ".agents" / "self-evolve"
    config_dir.mkdir(parents=True)
    (config_dir / "config.jsonc").write_text(
        json.dumps({"plugin_id": "self-evolve", "config_version": 4}),
        encoding="utf-8",
    )
    assert load_config(tmp_path) is None


def test_find_project_root_with_evolve_dir(tmp_path: Path):
    (tmp_path / ".agents" / "self-evolve").mkdir(parents=True)
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    found = find_project_root(sub)
    assert found == tmp_path


def test_find_project_root_returns_none(tmp_path: Path):
    sub = tmp_path / "empty"
    sub.mkdir()
    assert find_project_root(sub) is None
```

---

### Task 20: 创建 test_storage.py

**Files:**
- Create: `packages/self-evolve/tests/test_storage.py`

- [ ] **Step 1: 编写存储测试**

```python
from pathlib import Path

from self_evolve.models import KnowledgeRule
from self_evolve.storage import list_rules, load_rule, save_rule


def _make_rule(rule_id: str = "R-001", status: str = "active") -> KnowledgeRule:
    return KnowledgeRule(
        id=rule_id,
        created_at="2026-03-31T12:00:00Z",
        status=status,
        title="Test",
        statement="S",
        rationale="R",
        domain="testing",
        tags=["ci"],
    )


def test_save_and_load_rule(tmp_path: Path):
    rule = _make_rule()
    path = save_rule(tmp_path, rule)
    assert path.exists()
    loaded = load_rule(tmp_path, "R-001")
    assert loaded is not None
    assert loaded.id == "R-001"
    assert loaded.title == "Test"


def test_load_rule_returns_none_when_missing(tmp_path: Path):
    assert load_rule(tmp_path, "R-999") is None


def test_list_rules(tmp_path: Path):
    save_rule(tmp_path, _make_rule("R-001"))
    save_rule(tmp_path, _make_rule("R-002"))
    rules = list_rules(tmp_path)
    assert len(rules) == 2
    assert rules[0].id == "R-001"
    assert rules[1].id == "R-002"


def test_list_rules_empty(tmp_path: Path):
    assert list_rules(tmp_path) == []
```

---

### Task 21: 创建 test_scripts.py

**Files:**
- Create: `packages/self-evolve/tests/test_scripts.py`

- [ ] **Step 1: 编写脚本集成测试**

使用 `subprocess.run` 调用脚本（模拟真实使用场景），设置前先在 `tmp_path` 下创建 `.agents/skills/self-evolve/scripts/` 目录并复制脚本。

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
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "Always test.", "--rationale", "R", "--domain", "testing"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T2", "--statement", "Always test.", "--rationale", "R2", "--domain", "testing"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Warning" in result.stderr


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

### Task 22: 创建 test_sync.py

**Files:**
- Create: `packages/self-evolve/tests/test_sync.py`

- [ ] **Step 1: 编写 sync 测试**

```python
import json
from pathlib import Path

from self_evolve.config import SelfEvolveConfig, save_config
from self_evolve.models import KnowledgeRule
from self_evolve.storage import save_rule
from self_evolve.sync import sync_skill


def _init_project(tmp_path: Path, language: str = "en") -> None:
    save_config(tmp_path, SelfEvolveConfig(language=language))


def _make_rule(
    rule_id: str = "R-001",
    domain: str = "testing",
    status: str = "active",
) -> KnowledgeRule:
    return KnowledgeRule(
        id=rule_id,
        created_at="2026-03-31T12:00:00Z",
        status=status,
        title=f"Rule {rule_id}",
        statement="Test statement.",
        rationale="Test rationale.",
        domain=domain,
        tags=["ci"],
    )


def test_sync_generates_skill_md(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    assert result.path.exists()
    assert result.rules_count == 1
    assert result.strategy == "inline"
    content = result.path.read_text(encoding="utf-8")
    assert "R-001" in content


def test_sync_generates_catalog_v1(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    assert result.catalog_path is not None
    catalog = json.loads(result.catalog_path.read_text(encoding="utf-8"))
    assert catalog["version"] == 1
    assert catalog["summary"]["total_rules"] == 1
    assert len(catalog["rules"]) == 1
    rule_entry = catalog["rules"][0]
    assert "source_sessions" not in rule_entry
    assert "source_candidates" not in rule_entry


def test_sync_only_includes_active_rules(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule("R-001", status="active"))
    save_rule(tmp_path, _make_rule("R-002", status="retired"))
    result = sync_skill(tmp_path)
    assert result.rules_count == 1


def test_sync_index_strategy(tmp_path: Path):
    _init_project(tmp_path)
    for i in range(25):
        save_rule(tmp_path, _make_rule(f"R-{i + 1:03d}"))
    result = sync_skill(tmp_path, inline_threshold=20)
    assert result.strategy == "index"
    assert len(result.domain_files) > 0


def test_sync_copies_all_scripts(tmp_path: Path):
    _init_project(tmp_path)
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    script_names = {p.name for p in result.script_paths}
    assert "find_rules.py" in script_names
    assert "add_rule.py" in script_names
    assert "edit_rule.py" in script_names
    assert "retire_rule.py" in script_names
    assert "list_rules.py" in script_names


def test_sync_empty_project(tmp_path: Path):
    _init_project(tmp_path)
    result = sync_skill(tmp_path)
    assert result.rules_count == 0
    assert result.strategy == "inline"


def test_sync_uses_zh_cn_template(tmp_path: Path):
    _init_project(tmp_path, language="zh-CN")
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    content = result.path.read_text(encoding="utf-8")
    assert "项目知识规则" in content or "规则" in content


def test_sync_falls_back_to_agent_kit_lang(tmp_path: Path, monkeypatch):
    save_config(tmp_path, SelfEvolveConfig(language=None))
    monkeypatch.setenv("AGENT_KIT_LANG", "zh-CN")
    save_rule(tmp_path, _make_rule())
    result = sync_skill(tmp_path)
    assert result.path.exists()
```

- [ ] **Step 2: 运行全部测试**

Run: `uv run pytest packages/self-evolve/tests -q`
Expected: 所有测试通过

- [ ] **Step 3: 提交 Chunk 6**

```bash
git add -A packages/self-evolve/tests/
git commit -m "test(self-evolve): v5 全量测试从零编写——models/config/storage/scripts/sync"
```

---

## Chunk 7: 文档与版本

### Task 23: 更新 pyproject.toml

**Files:**
- Modify: `packages/self-evolve/pyproject.toml`

- [ ] **Step 1: 版本号升级**

```toml
version = "0.5.0"
```

`force-include` 已包含 `scripts` 目录，无需额外修改。

---

### Task 24: 重写 AGENTS.md

**Files:**
- Rewrite: `packages/self-evolve/AGENTS.md`

- [ ] **Step 1: 编写 v5 AGENTS.md**

关键变化：
- 插件目标改为 Rule-only 架构描述
- 命令列表只有 `init`、`sync`、`status`
- 配置字段只有 `plugin_id`、`config_version`、`language`、`inline_threshold`
- `config_version` 固定为 5
- 数据存储只有 `rules/` 目录
- 核心概念只有 Rule 和脚本层
- 不提及任何旧版本检测、旧格式标记、旧命令兼容
- Skill 同步输出增加 `scripts/` 目录说明
- 验证要点聚焦于脚本层、反思注入模板、sync 输出

---

### Task 25: 重写 README.md

**Files:**
- Rewrite: `packages/self-evolve/README.md`

- [ ] **Step 1: 重写为 v5 架构**

反映新的 `Agent → 脚本 → Rule → sync → SKILL.md` 流程。核心模型只有 Rule。命令只有 init/sync/status。脚本层作为 Agent 接口。

---

### Task 26: 重写 USAGE.md

**Files:**
- Rewrite: `packages/self-evolve/USAGE.md`

- [ ] **Step 1: 重写为 v5 使用指南**

重点放在：
1. 初始化项目
2. 通过 Skill 触发反思注入
3. 直接使用脚本管理规则
4. 同步到 Skill 输出
5. 通过 Git diff 审核

---

### Task 27: 归档旧文档

**Files:**
- Modify: `packages/self-evolve/docs/详细说明.md`

- [ ] **Step 1: 在文件头标记归档**

```markdown
> ⚠️ 本文档描述的是 v4 架构，已被 v5 彻底重写取代。仅供历史参考。v5 使用指南见 `USAGE.md`。
```

---

### Task 28: 最终验证与提交

- [ ] **Step 1: 运行全部测试**

Run: `uv run pytest packages/self-evolve/tests -q`
Expected: 所有测试通过

- [ ] **Step 2: 提交文档与版本号**

```bash
git add -A packages/self-evolve/
git commit -m "docs(self-evolve): v5 文档与版本号——AGENTS/README/USAGE 全部重写"
```
