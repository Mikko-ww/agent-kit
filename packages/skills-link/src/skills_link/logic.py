from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys

from skills_link.config import SkillLinkConfig, TargetConfig

SUPPORTED_PLATFORMS = ("darwin", "linux")


@dataclass(slots=True, frozen=True)
class TargetSkillStatus:
    target_name: str
    target_path: Path
    status: str


@dataclass(slots=True, frozen=True)
class SkillStatus:
    name: str
    source_path: Path
    target_statuses: list[TargetSkillStatus]


@dataclass(slots=True, frozen=True)
class SkillTargetResult:
    skill_name: str
    target_name: str
    target_path: Path


@dataclass(slots=True, frozen=True)
class LinkResult:
    linked: list[SkillTargetResult]
    conflicts: list[SkillTargetResult]


@dataclass(slots=True, frozen=True)
class UnlinkResult:
    unlinked: list[SkillTargetResult]
    skipped: list[SkillTargetResult]


@dataclass(slots=True, frozen=True)
class TargetSummary:
    name: str
    path: Path
    available: bool
    managed_links: int
    linked: int
    not_linked: int
    broken_link: int
    conflict: int


def ensure_supported_platform() -> None:
    if not sys.platform.startswith(SUPPORTED_PLATFORMS):
        raise RuntimeError("skills-link is only supported on macOS and Linux")


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


def discover_skill_statuses(config: SkillLinkConfig, target_names: list[str] | None = None) -> list[SkillStatus]:
    validate_source_dir(config.source_dir)
    targets = _resolve_targets(config, target_names)
    return [
        SkillStatus(
            name=skill_dir.name,
            source_path=skill_dir,
            target_statuses=[
                TargetSkillStatus(
                    target_name=target.name,
                    target_path=target.path / skill_dir.name,
                    status=_resolve_status(skill_dir, target.path / skill_dir.name),
                )
                for target in targets
            ],
        )
        for skill_dir in _discover_skill_dirs(config.source_dir)
    ]


def summarize_targets(config: SkillLinkConfig, target_names: list[str] | None = None) -> list[TargetSummary]:
    validate_source_dir(config.source_dir)
    targets = _resolve_targets(config, target_names)
    skill_statuses = discover_skill_statuses(config, target_names=[target.name for target in targets])
    summaries: list[TargetSummary] = []

    for target in targets:
        counts = {
            "linked": 0,
            "not_linked": 0,
            "broken_link": 0,
            "conflict": 0,
        }
        for skill in skill_statuses:
            for target_status in skill.target_statuses:
                if target_status.target_name == target.name:
                    counts[target_status.status] += 1
        summaries.append(
            TargetSummary(
                name=target.name,
                path=target.path,
                available=target.path.exists() and target.path.is_dir(),
                managed_links=counts["linked"],
                linked=counts["linked"],
                not_linked=counts["not_linked"],
                broken_link=counts["broken_link"],
                conflict=counts["conflict"],
            )
        )

    return summaries


def link_skills(
    config: SkillLinkConfig,
    selected_skill_names: list[str],
    target_names: list[str] | None = None,
) -> LinkResult:
    validate_source_dir(config.source_dir)
    targets = _resolve_targets(config, target_names)
    for target in targets:
        validate_target_dir(target.path)

    statuses = {
        item.name: item for item in discover_skill_statuses(config, target_names=[target.name for target in targets])
    }
    linked: list[SkillTargetResult] = []
    conflicts: list[SkillTargetResult] = []

    for name in selected_skill_names:
        skill_status = statuses.get(name)
        if skill_status is None:
            for target in targets:
                conflicts.append(
                    SkillTargetResult(skill_name=name, target_name=target.name, target_path=target.path / name)
                )
            continue
        for target_status in skill_status.target_statuses:
            if target_status.status != "not_linked":
                conflicts.append(
                    SkillTargetResult(
                        skill_name=name,
                        target_name=target_status.target_name,
                        target_path=target_status.target_path,
                    )
                )
                continue
            target_status.target_path.symlink_to(skill_status.source_path, target_is_directory=True)
            linked.append(
                SkillTargetResult(
                    skill_name=name,
                    target_name=target_status.target_name,
                    target_path=target_status.target_path,
                )
            )

    return LinkResult(linked=linked, conflicts=conflicts)


def unlink_skills(
    config: SkillLinkConfig,
    selected_skill_names: list[str],
    target_names: list[str] | None = None,
) -> UnlinkResult:
    validate_source_dir(config.source_dir)
    targets = _resolve_targets(config, target_names)
    for target in targets:
        validate_target_dir(target.path)
    unlinked: list[SkillTargetResult] = []
    skipped: list[SkillTargetResult] = []

    for name in selected_skill_names:
        for target in targets:
            source_path = config.source_dir / name
            target_path = target.path / name
            if _is_managed_link(target_path, source_path):
                target_path.unlink()
                unlinked.append(
                    SkillTargetResult(skill_name=name, target_name=target.name, target_path=target_path)
                )
                continue
            skipped.append(
                SkillTargetResult(skill_name=name, target_name=target.name, target_path=target_path)
            )

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


def _resolve_targets(config: SkillLinkConfig, target_names: list[str] | None) -> list[TargetConfig]:
    if not target_names:
        return list(config.targets)

    targets_by_name = {target.name: target for target in config.targets}
    resolved: list[TargetConfig] = []
    seen_names: set[str] = set()
    missing_names: list[str] = []

    for name in target_names:
        if name in seen_names:
            continue
        target = targets_by_name.get(name)
        if target is None:
            missing_names.append(name)
            continue
        seen_names.add(name)
        resolved.append(target)

    if missing_names:
        raise ValueError(f"unknown target(s): {', '.join(missing_names)}")

    return resolved


def add_target(config: SkillLinkConfig, target: TargetConfig) -> SkillLinkConfig:
    if any(existing.name == target.name for existing in config.targets):
        raise ValueError(f"duplicate target name: {target.name}")
    return SkillLinkConfig(source_dir=config.source_dir, targets=[*config.targets, target])


def update_target(
    config: SkillLinkConfig,
    name: str,
    *,
    new_name: str | None = None,
    new_path: Path | None = None,
) -> SkillLinkConfig:
    target = _resolve_single_target(config, name)
    if new_name and new_name != name and any(existing.name == new_name for existing in config.targets):
        raise ValueError(f"duplicate target name: {new_name}")
    if new_path is not None and new_path != target.path and _count_managed_links(config, target) > 0:
        raise ValueError(f"cannot change path for target {name}; run unlink --target {name} first")

    updated = TargetConfig(
        name=new_name or target.name,
        path=new_path or target.path,
    )
    return SkillLinkConfig(
        source_dir=config.source_dir,
        targets=[updated if existing.name == name else existing for existing in config.targets],
    )


def remove_target(config: SkillLinkConfig, name: str) -> SkillLinkConfig:
    target = _resolve_single_target(config, name)
    if _count_managed_links(config, target) > 0:
        raise ValueError(f"cannot remove target {name}; run unlink --target {name} first")

    return SkillLinkConfig(
        source_dir=config.source_dir,
        targets=[existing for existing in config.targets if existing.name != name],
    )


def _resolve_single_target(config: SkillLinkConfig, name: str) -> TargetConfig:
    targets = _resolve_targets(config, [name])
    return targets[0]


def _count_managed_links(config: SkillLinkConfig, target: TargetConfig) -> int:
    validate_source_dir(config.source_dir)
    validate_target_dir(target.path)

    count = 0
    for skill_dir in _discover_skill_dirs(config.source_dir):
        if _is_managed_link(target.path / skill_dir.name, skill_dir):
            count += 1
    return count
