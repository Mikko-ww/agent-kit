from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SessionRecord:
    id: str
    created_at: str
    source: str
    summary: str
    domain: str
    outcome: str
    observations: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    processed: bool = False
    amended_from: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "source": self.source,
            "summary": self.summary,
            "domain": self.domain,
            "outcome": self.outcome,
            "observations": list(self.observations),
            "decisions": list(self.decisions),
            "fixes": list(self.fixes),
            "lessons": list(self.lessons),
            "files": list(self.files),
            "tags": list(self.tags),
            "processed": self.processed,
            "amended_from": self.amended_from,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> SessionRecord:
        return cls(
            id=str(data.get("id", "")),
            created_at=str(data.get("created_at", "")),
            source=str(data.get("source", "agent")),
            summary=str(data.get("summary", "")),
            domain=str(data.get("domain", "")),
            outcome=str(data.get("outcome", "partial")),
            observations=list(data.get("observations", [])),  # type: ignore[arg-type]
            decisions=list(data.get("decisions", [])),  # type: ignore[arg-type]
            fixes=list(data.get("fixes", [])),  # type: ignore[arg-type]
            lessons=list(data.get("lessons", [])),  # type: ignore[arg-type]
            files=list(data.get("files", [])),  # type: ignore[arg-type]
            tags=list(data.get("tags", [])),  # type: ignore[arg-type]
            processed=bool(data.get("processed", False)),
            amended_from=str(data.get("amended_from", "")),
        )


@dataclass(slots=True)
class KnowledgeCandidate:
    id: str
    created_at: str
    status: str
    title: str
    statement: str
    rationale: str
    domain: str
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    fingerprint: str = ""
    source_session_ids: list[str] = field(default_factory=list)
    derived_from: str = ""

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
            "confidence": self.confidence,
            "fingerprint": self.fingerprint,
            "source_session_ids": list(self.source_session_ids),
            "derived_from": self.derived_from,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> KnowledgeCandidate:
        return cls(
            id=str(data.get("id", "")),
            created_at=str(data.get("created_at", "")),
            status=str(data.get("status", "open")),
            title=str(data.get("title", "")),
            statement=str(data.get("statement", "")),
            rationale=str(data.get("rationale", "")),
            domain=str(data.get("domain", "")),
            tags=list(data.get("tags", [])),  # type: ignore[arg-type]
            confidence=float(data.get("confidence", 0.0)),
            fingerprint=str(data.get("fingerprint", "")),
            source_session_ids=list(data.get("source_session_ids", [])),  # type: ignore[arg-type]
            derived_from=str(data.get("derived_from", "")),
        )


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
    source_session_ids: list[str] = field(default_factory=list)
    source_candidate_ids: list[str] = field(default_factory=list)
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
            "source_session_ids": list(self.source_session_ids),
            "source_candidate_ids": list(self.source_candidate_ids),
            "revision_of": self.revision_of,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> KnowledgeRule:
        return cls(
            id=str(data.get("id", "")),
            created_at=str(data.get("created_at", "")),
            status=str(data.get("status", "active")),
            title=str(data.get("title", "")),
            statement=str(data.get("statement", "")),
            rationale=str(data.get("rationale", "")),
            domain=str(data.get("domain", "")),
            tags=list(data.get("tags", [])),  # type: ignore[arg-type]
            source_session_ids=list(data.get("source_session_ids", [])),  # type: ignore[arg-type]
            source_candidate_ids=list(data.get("source_candidate_ids", [])),  # type: ignore[arg-type]
            revision_of=str(data.get("revision_of", "")),
        )


@dataclass(slots=True)
class KnowledgeIndex:
    fingerprint_to_candidate_ids: dict[str, list[str]] = field(default_factory=dict)
    fingerprint_to_rule_ids: dict[str, list[str]] = field(default_factory=dict)
    session_to_candidate_ids: dict[str, list[str]] = field(default_factory=dict)
    candidate_to_rule_id: dict[str, str] = field(default_factory=dict)
    active_rule_by_fingerprint: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "fingerprint_to_candidate_ids": {
                key: list(value) for key, value in self.fingerprint_to_candidate_ids.items()
            },
            "fingerprint_to_rule_ids": {
                key: list(value) for key, value in self.fingerprint_to_rule_ids.items()
            },
            "session_to_candidate_ids": {
                key: list(value) for key, value in self.session_to_candidate_ids.items()
            },
            "candidate_to_rule_id": dict(self.candidate_to_rule_id),
            "active_rule_by_fingerprint": dict(self.active_rule_by_fingerprint),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> KnowledgeIndex:
        return cls(
            fingerprint_to_candidate_ids={
                str(key): list(value)
                for key, value in dict(data.get("fingerprint_to_candidate_ids", {})).items()  # type: ignore[arg-type]
            },
            fingerprint_to_rule_ids={
                str(key): list(value)
                for key, value in dict(data.get("fingerprint_to_rule_ids", {})).items()  # type: ignore[arg-type]
            },
            session_to_candidate_ids={
                str(key): list(value)
                for key, value in dict(data.get("session_to_candidate_ids", {})).items()  # type: ignore[arg-type]
            },
            candidate_to_rule_id={
                str(key): str(value)
                for key, value in dict(data.get("candidate_to_rule_id", {})).items()  # type: ignore[arg-type]
            },
            active_rule_by_fingerprint={
                str(key): str(value)
                for key, value in dict(data.get("active_rule_by_fingerprint", {})).items()  # type: ignore[arg-type]
            },
        )
