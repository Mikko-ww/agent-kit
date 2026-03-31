from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


VALID_PRIORITIES = ("low", "medium", "high", "critical")
VALID_STATUSES = ("active", "resolved", "promoted", "promoted_to_skill")


@dataclass(slots=True)
class LearningEntry:
    id: str
    timestamp: str
    priority: str
    status: str
    domain: str
    summary: str
    detail: str = ""
    suggested_action: str = ""
    pattern_key: str = ""
    see_also: list[str] = field(default_factory=list)
    recurrence_count: int = 1
    task_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "status": self.status,
            "domain": self.domain,
            "summary": self.summary,
            "detail": self.detail,
            "suggested_action": self.suggested_action,
            "pattern_key": self.pattern_key,
            "see_also": list(self.see_also),
            "recurrence_count": self.recurrence_count,
            "task_ids": list(self.task_ids),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LearningEntry:
        return cls(
            id=str(data.get("id", "")),
            timestamp=str(data.get("timestamp", "")),
            priority=str(data.get("priority", "medium")),
            status=str(data.get("status", "active")),
            domain=str(data.get("domain", "")),
            summary=str(data.get("summary", "")),
            detail=str(data.get("detail", "")),
            suggested_action=str(data.get("suggested_action", "")),
            pattern_key=str(data.get("pattern_key", "")),
            see_also=list(data.get("see_also", [])),  # type: ignore[arg-type]
            recurrence_count=int(data.get("recurrence_count", 1)),  # type: ignore[arg-type]
            task_ids=list(data.get("task_ids", [])),  # type: ignore[arg-type]
            tags=list(data.get("tags", [])),  # type: ignore[arg-type]
            metadata=dict(data.get("metadata", {})),  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class PromotedRule:
    id: str
    source_learning_id: str
    rule: str
    domain: str
    created_at: str
    tags: list[str] = field(default_factory=list)
    title: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_learning_id": self.source_learning_id,
            "rule": self.rule,
            "domain": self.domain,
            "created_at": self.created_at,
            "tags": list(self.tags),
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> PromotedRule:
        return cls(
            id=str(data.get("id", "")),
            source_learning_id=str(data.get("source_learning_id", "")),
            rule=str(data.get("rule", "")),
            domain=str(data.get("domain", "")),
            created_at=str(data.get("created_at", "")),
            tags=list(data.get("tags", [])),  # type: ignore[arg-type]
            title=str(data.get("title", "")),
        )


def generate_learning_id(existing_ids: list[str]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"L-{today}-"
    max_seq = 0
    for eid in existing_ids:
        if eid.startswith(prefix):
            try:
                seq = int(eid[len(prefix):])
                max_seq = max(max_seq, seq)
            except ValueError:
                continue
    return f"{prefix}{max_seq + 1:03d}"


def generate_rule_id(existing_ids: list[str]) -> str:
    max_seq = 0
    for eid in existing_ids:
        if eid.startswith("R-"):
            try:
                seq = int(eid[2:])
                max_seq = max(max_seq, seq)
            except ValueError:
                continue
    return f"R-{max_seq + 1:03d}"
