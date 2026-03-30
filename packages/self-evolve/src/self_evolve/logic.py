from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from self_evolve.config import ProjectConfig
from self_evolve.jsonc import load_jsonc, write_jsonc

VALID_CATEGORIES = ("rule", "pattern", "learning")

SELF_EVOLVE_SKILL_MD = """\
# self-evolve

项目级自我进化技能。智能体可通过此技能捕获学习记录、查阅已有规则与模式，持续积累项目知识。

## 使用方式

### 捕获记忆

当你在工作中发现值得记录的规则、模式或学习经验时，使用以下命令捕获：

```bash
agent-kit self-evolve capture --category <rule|pattern|learning> --subject "<主题>" --content "<内容>" [--source "<来源>"]
```

### 查阅记忆

在开始任务前，查阅已有的规则和模式：

```bash
agent-kit self-evolve list [--category <rule|pattern|learning>]
agent-kit self-evolve show <id>
```

### 查看状态

```bash
agent-kit self-evolve status
```

## 类别说明

- **rule**: 必须遵守的项目规则和约束
- **pattern**: 项目中反复出现的代码模式
- **learning**: 从实践中获得的经验教训

## 建议

- 完成代码审查后，将发现的规则捕获为 `rule`
- 重构时识别到的代码模式记录为 `pattern`
- 调试或解决问题后的经验记录为 `learning`
"""


@dataclass(slots=True, frozen=True)
class Memory:
    id: str
    category: str
    subject: str
    content: str
    source: str
    created_at: str


@dataclass(slots=True, frozen=True)
class SkillInfo:
    name: str
    path: Path
    description: str


@dataclass(slots=True, frozen=True)
class StatusSummary:
    project_root: Path
    total_memories: int
    rules: int
    patterns: int
    learnings: int
    skills: int


def validate_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"invalid category: {category}")


def init_agent_dir(project_root: Path) -> Path:
    """初始化 .agent 目录结构，返回 .agent 目录路径。"""
    agent_dir = project_root / ".agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memories").mkdir(exist_ok=True)
    (agent_dir / "skills").mkdir(exist_ok=True)
    # 生成自我进化技能描述文件
    skill_dir = agent_dir / "skills" / "self-evolve"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(SELF_EVOLVE_SKILL_MD, encoding="utf-8")
    return agent_dir


def is_initialized(project_root: Path) -> bool:
    agent_dir = project_root / ".agent"
    return agent_dir.exists() and agent_dir.is_dir()


def capture_memory(
    config: ProjectConfig,
    *,
    category: str,
    subject: str,
    content: str,
    source: str = "",
) -> Memory:
    validate_category(category)
    memory_id = _next_memory_id(config.memories_dir)
    now = datetime.now(timezone.utc).isoformat()
    memory = Memory(
        id=memory_id,
        category=category,
        subject=subject,
        content=content,
        source=source,
        created_at=now,
    )
    write_jsonc(
        config.memories_dir / f"{memory_id}.jsonc",
        {
            "id": memory.id,
            "category": memory.category,
            "subject": memory.subject,
            "content": memory.content,
            "source": memory.source,
            "created_at": memory.created_at,
        },
    )
    return memory


def list_memories(config: ProjectConfig, *, category: str | None = None) -> list[Memory]:
    memories: list[Memory] = []
    if not config.memories_dir.exists():
        return memories
    for path in sorted(config.memories_dir.iterdir()):
        if not path.name.endswith(".jsonc"):
            continue
        memory = _load_memory(path)
        if memory is None:
            continue
        if category is not None and memory.category != category:
            continue
        memories.append(memory)
    return memories


def get_memory(config: ProjectConfig, memory_id: str) -> Memory | None:
    path = config.memories_dir / f"{memory_id}.jsonc"
    if not path.exists():
        return None
    return _load_memory(path)


def list_skills(config: ProjectConfig) -> list[SkillInfo]:
    skills: list[SkillInfo] = []
    if not config.skills_dir.exists():
        return skills
    for child in sorted(config.skills_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.is_file():
            continue
        description = _extract_skill_description(skill_file)
        skills.append(SkillInfo(name=child.name, path=child, description=description))
    return skills


def get_skill(config: ProjectConfig, name: str) -> SkillInfo | None:
    skill_dir = config.skills_dir / name
    if not skill_dir.is_dir():
        return None
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return None
    description = _extract_skill_description(skill_file)
    return SkillInfo(name=name, path=skill_dir, description=description)


def get_status(config: ProjectConfig) -> StatusSummary:
    memories = list_memories(config)
    skills = list_skills(config)
    return StatusSummary(
        project_root=config.project_root,
        total_memories=len(memories),
        rules=sum(1 for m in memories if m.category == "rule"),
        patterns=sum(1 for m in memories if m.category == "pattern"),
        learnings=sum(1 for m in memories if m.category == "learning"),
        skills=len(skills),
    )


def _next_memory_id(memories_dir: Path) -> str:
    if not memories_dir.exists():
        return "m-001"
    existing = [
        p.stem for p in memories_dir.glob("m-*.jsonc")
    ]
    if not existing:
        return "m-001"
    numbers = []
    for name in existing:
        try:
            numbers.append(int(name.split("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    next_num = max(numbers) + 1 if numbers else 1
    return f"m-{next_num:03d}"


def _load_memory(path: Path) -> Memory | None:
    try:
        data = load_jsonc(path)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    required = ("id", "category", "subject", "content")
    if not all(isinstance(data.get(k), str) for k in required):
        return None
    return Memory(
        id=data["id"],
        category=data["category"],
        subject=data["subject"],
        content=data["content"],
        source=data.get("source", ""),
        created_at=data.get("created_at", ""),
    )


def _extract_skill_description(skill_file: Path) -> str:
    """从 SKILL.md 中提取第一行非标题文本作为描述。"""
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    return ""
