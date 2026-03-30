from __future__ import annotations

from pathlib import Path

from self_evolve.jsonc import load_jsonc, write_jsonc
from self_evolve.models import LearningEntry, PromotedRule


def learnings_dir(data_root: Path) -> Path:
    return data_root / "plugins" / "self-evolve" / "learnings"


def rules_file(data_root: Path) -> Path:
    return data_root / "plugins" / "self-evolve" / "rules.jsonc"


def save_learning(data_root: Path, entry: LearningEntry) -> Path:
    target_dir = learnings_dir(data_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{entry.id}.jsonc"
    write_jsonc(path, entry.to_dict())
    return path


def load_learning(data_root: Path, learning_id: str) -> LearningEntry | None:
    path = learnings_dir(data_root) / f"{learning_id}.jsonc"
    if not path.exists():
        return None
    data = load_jsonc(path)
    if not isinstance(data, dict):
        return None
    return LearningEntry.from_dict(data)


def list_learnings(data_root: Path) -> list[LearningEntry]:
    target_dir = learnings_dir(data_root)
    if not target_dir.exists():
        return []
    entries: list[LearningEntry] = []
    for path in sorted(target_dir.iterdir()):
        if path.suffix != ".jsonc":
            continue
        try:
            data = load_jsonc(path)
            if isinstance(data, dict):
                entries.append(LearningEntry.from_dict(data))
        except Exception:
            continue
    return entries


def list_learning_ids(data_root: Path) -> list[str]:
    target_dir = learnings_dir(data_root)
    if not target_dir.exists():
        return []
    ids: list[str] = []
    for path in sorted(target_dir.iterdir()):
        if path.suffix == ".jsonc":
            ids.append(path.stem)
    return ids


def save_rules(data_root: Path, rules: list[PromotedRule]) -> Path:
    path = rules_file(data_root)
    write_jsonc(path, {"rules": [r.to_dict() for r in rules]})
    return path


def load_rules(data_root: Path) -> list[PromotedRule]:
    path = rules_file(data_root)
    if not path.exists():
        return []
    try:
        data = load_jsonc(path)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        return []
    return [PromotedRule.from_dict(r) for r in raw_rules if isinstance(r, dict)]
