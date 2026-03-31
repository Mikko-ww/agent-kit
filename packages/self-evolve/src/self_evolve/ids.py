from __future__ import annotations

from datetime import datetime, timezone


def generate_session_id(existing_ids: list[str], *, now_utc: str | None = None) -> str:
    today = now_utc or datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"S-{today}-"
    return f"{prefix}{_max_suffix(existing_ids, prefix) + 1:03d}"


def generate_candidate_id(existing_ids: list[str]) -> str:
    return f"C-{_max_suffix(existing_ids, 'C-') + 1:03d}"


def generate_rule_id(existing_ids: list[str]) -> str:
    return f"R-{_max_suffix(existing_ids, 'R-') + 1:03d}"


def _max_suffix(existing_ids: list[str], prefix: str) -> int:
    max_seq = 0
    for item in existing_ids:
        if not item.startswith(prefix):
            continue
        try:
            seq = int(item[len(prefix):])
        except ValueError:
            continue
        max_seq = max(max_seq, seq)
    return max_seq
