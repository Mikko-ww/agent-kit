from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys

from agent_kit_skill_link.config import SkillLinkConfig

SUPPORTED_PLATFORMS = ("darwin", "linux")


@dataclass(slots=True, frozen=True)
class SkillStatus:
    name: str
    source_path: Path
    target_path: Path
    status: str


@dataclass(slots=True, frozen=True)
class LinkResult:
    linked: list[str]
    conflicts: list[str]


@dataclass(slots=True, frozen=True)
class UnlinkResult:
    unlinked: list[str]
    skipped: list[str]


def ensure_supported_platform() -> None:
    if not sys.platform.startswith(SUPPORTED_PLATFORMS):
        raise RuntimeError("skill-link is only supported on macOS and Linux")


def validate_source_dir(source_dir: Path) -> None:
    if not source_dir.exists():
        raise ValueError(f"source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"source path is not a directory: {source_dir}")
    if not os.access(source_dir, os.R_OK):
        raise ValueError(f"source directory is not readable: {source_dir}")


def validate_target_dir(target_dir: Path) -> None:
    if target_dir.exists() and not target_dir.is_dir():
        raise ValueError(f"target path is not a directory: {target_dir}")


def discover_skill_statuses(config: SkillLinkConfig) -> list[SkillStatus]:
    validate_source_dir(config.source_dir)
    return [
        SkillStatus(
            name=skill_dir.name,
            source_path=skill_dir,
            target_path=config.target_dir / skill_dir.name,
            status=_resolve_status(skill_dir, config.target_dir / skill_dir.name),
        )
        for skill_dir in _discover_skill_dirs(config.source_dir)
    ]


def link_skills(config: SkillLinkConfig, selected_skill_names: list[str]) -> LinkResult:
    validate_source_dir(config.source_dir)
    validate_target_dir(config.target_dir)
    statuses = {
        item.name: item for item in discover_skill_statuses(config)
    }
    linked: list[str] = []
    conflicts: list[str] = []

    for name in selected_skill_names:
        status = statuses.get(name)
        if status is None or status.status != "not_linked":
            conflicts.append(name)
            continue
        status.target_path.symlink_to(status.source_path, target_is_directory=True)
        linked.append(name)

    return LinkResult(linked=linked, conflicts=conflicts)


def unlink_skills(config: SkillLinkConfig, selected_skill_names: list[str]) -> UnlinkResult:
    validate_source_dir(config.source_dir)
    validate_target_dir(config.target_dir)
    unlinked: list[str] = []
    skipped: list[str] = []

    for name in selected_skill_names:
        source_path = config.source_dir / name
        target_path = config.target_dir / name
        if _is_managed_link(target_path, source_path):
            target_path.unlink()
            unlinked.append(name)
            continue
        skipped.append(name)

    return UnlinkResult(unlinked=unlinked, skipped=skipped)


def _discover_skill_dirs(source_dir: Path) -> list[Path]:
    skill_dirs: list[Path] = []
    for child in sorted(source_dir.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        if (child / "SKILL.md").is_file():
            skill_dirs.append(child)
    return skill_dirs


def _resolve_status(source_path: Path, target_path: Path) -> str:
    if target_path.is_symlink():
        if not target_path.exists():
            return "broken_link"
        if target_path.resolve() == source_path.resolve():
            return "linked"
        return "conflict"
    if target_path.exists():
        return "conflict"
    return "not_linked"


def _is_managed_link(target_path: Path, source_path: Path) -> bool:
    return (
        target_path.is_symlink()
        and target_path.exists()
        and target_path.resolve() == source_path.resolve()
    )
