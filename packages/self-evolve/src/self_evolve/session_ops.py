from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from self_evolve.config import (
    SelfEvolveConfig,
    candidates_dir,
    ensure_no_legacy_layout,
    indexes_dir,
    rules_dir,
    save_config,
    sessions_dir,
)
from self_evolve.ids import generate_session_id
from self_evolve.index_ops import rebuild_knowledge_index
from self_evolve.models import SessionRecord
from self_evolve.storage import list_sessions, save_session


def initialize_project(project_root: Path, config: SelfEvolveConfig) -> None:
    ensure_no_legacy_layout(project_root)
    sessions_dir(project_root).mkdir(parents=True, exist_ok=True)
    candidates_dir(project_root).mkdir(parents=True, exist_ok=True)
    rules_dir(project_root).mkdir(parents=True, exist_ok=True)
    indexes_dir(project_root).mkdir(parents=True, exist_ok=True)
    save_config(project_root, config)
    rebuild_knowledge_index(project_root)


def record_session(
    project_root: Path,
    *,
    summary: str,
    domain: str,
    outcome: str,
    source: str = "agent",
    observations: list[str] | None = None,
    decisions: list[str] | None = None,
    fixes: list[str] | None = None,
    lessons: list[str] | None = None,
    files: list[str] | None = None,
    tags: list[str] | None = None,
    created_at: str | None = None,
) -> SessionRecord:
    existing_ids = [session.id for session in list_sessions(project_root)]
    session = SessionRecord(
        id=generate_session_id(existing_ids),
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        source=source,
        summary=summary,
        domain=domain,
        outcome=outcome,
        observations=observations or [],
        decisions=decisions or [],
        fixes=fixes or [],
        lessons=lessons or [],
        files=files or [],
        tags=tags or [],
        processed=False,
    )
    save_session(project_root, session)
    return session
