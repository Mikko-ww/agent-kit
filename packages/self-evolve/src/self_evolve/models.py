"""数据模型——仅 KnowledgeRule。"""

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
