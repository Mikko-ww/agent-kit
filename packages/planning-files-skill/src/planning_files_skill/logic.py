from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from planning_files_skill import PLUGIN_ID, SKILL_NAME, __version__

SUPPORTED_PLATFORMS = ("codex", "cursor", "opencode", "generic")
SUPPORTED_LANGUAGES = ("en", "zh-CN")
SUPPORTED_SCOPES = ("project", "global")
MANIFEST_NAME = ".planning-files-skill.json"


class PlanningFilesError(ValueError):
    pass


class ResourceConflict(PlanningFilesError):
    pass


class HooksConfigError(PlanningFilesError):
    pass


@dataclass(frozen=True)
class ImportRequest:
    platform: str
    language: str
    scope: str
    project_root: Path
    home_dir: Path
    dry_run: bool = False
    force: bool = False


@dataclass(slots=True, frozen=True)
class FileAction:
    path: Path
    action: str


@dataclass(slots=True, frozen=True)
class ImportResult:
    platform: str
    scope: str
    skill_path: Path
    actions: list[FileAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(action.action not in {"unchanged"} for action in self.actions)


@dataclass(slots=True, frozen=True)
class PlatformStatus:
    platform: str
    scope: str
    skill_path: Path
    installed: bool
    language: str | None = None
    plugin_version: str | None = None


def import_platform(request: ImportRequest) -> ImportResult:
    platforms = _expand_platforms(request.platform)
    if len(platforms) > 1:
        actions: list[FileAction] = []
        warnings: list[str] = []
        first_path = target_skill_dir(platforms[0], request.scope, request.project_root, request.home_dir)
        for platform in platforms:
            result = import_platform(ImportRequest(**{**request.__dict__, "platform": platform}))
            actions.extend(result.actions)
            warnings.extend(result.warnings)
        return ImportResult(platform=request.platform, scope=request.scope, skill_path=first_path, actions=actions, warnings=warnings)

    platform = platforms[0]
    _validate_language(request.language)
    _validate_scope(request.scope)

    skill_path = target_skill_dir(platform, request.scope, request.project_root, request.home_dir)
    actions = _sync_skill_files(skill_path, request, platform)
    warnings: list[str] = []

    if platform in {"codex", "cursor"}:
        hooks_actions = _sync_hook_files(platform, request)
        actions.extend(hooks_actions)
        merge_action = _merge_hooks_config(platform, request)
        actions.append(merge_action)
        if platform == "codex":
            warnings.append("codex_hooks")

    return ImportResult(platform=platform, scope=request.scope, skill_path=skill_path, actions=actions, warnings=warnings)


def inspect_platform(*, platform: str, scope: str, project_root: Path, home_dir: Path) -> PlatformStatus:
    platforms = _expand_platforms(platform)
    if len(platforms) != 1:
        raise PlanningFilesError("status requires a single platform")
    _validate_scope(scope)
    skill_path = target_skill_dir(platforms[0], scope, project_root, home_dir)
    manifest_path = skill_path / MANIFEST_NAME
    if not manifest_path.exists():
        return PlatformStatus(platform=platforms[0], scope=scope, skill_path=skill_path, installed=False)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return PlatformStatus(platform=platforms[0], scope=scope, skill_path=skill_path, installed=False)
    if manifest.get("plugin_id") != PLUGIN_ID or manifest.get("skill_name") != SKILL_NAME:
        return PlatformStatus(platform=platforms[0], scope=scope, skill_path=skill_path, installed=False)
    return PlatformStatus(
        platform=platforms[0],
        scope=scope,
        skill_path=skill_path,
        installed=True,
        language=str(manifest.get("language") or ""),
        plugin_version=str(manifest.get("plugin_version") or ""),
    )


def target_skill_dir(platform: str, scope: str, project_root: Path, home_dir: Path) -> Path:
    _validate_scope(scope)
    platforms = _expand_platforms(platform)
    if len(platforms) != 1:
        raise PlanningFilesError("target path requires a single platform")
    platform = platforms[0]
    if scope == "project":
        project_targets = {
            "codex": project_root / ".codex" / "skills" / SKILL_NAME,
            "cursor": project_root / ".cursor" / "skills" / SKILL_NAME,
            "opencode": project_root / ".opencode" / "skills" / SKILL_NAME,
            "generic": project_root / ".agents" / "skills" / SKILL_NAME,
        }
        return project_targets[platform]
    global_targets = {
        "codex": home_dir / ".codex" / "skills" / SKILL_NAME,
        "cursor": home_dir / ".cursor" / "skills" / SKILL_NAME,
        "opencode": home_dir / ".config" / "opencode" / "skills" / SKILL_NAME,
        "generic": home_dir / ".agents" / "skills" / SKILL_NAME,
    }
    return global_targets[platform]


def _sync_skill_files(skill_path: Path, request: ImportRequest, platform: str) -> list[FileAction]:
    if skill_path.exists() and not (skill_path / MANIFEST_NAME).exists() and any(skill_path.iterdir()) and not request.force:
        raise ResourceConflict(f"unmanaged skill already exists: {skill_path}")

    resource_root = _resource_root() / "skills" / request.language
    resource_files = _resource_files(resource_root)
    managed_files = [str(relative) for relative, _ in resource_files]
    actions: list[FileAction] = []

    for relative, content in resource_files:
        actions.append(_write_text(skill_path / relative, content, request.dry_run))

    manifest = {
        "plugin_id": PLUGIN_ID,
        "plugin_version": __version__,
        "skill_name": SKILL_NAME,
        "platform": platform,
        "scope": request.scope,
        "language": request.language,
        "managed_files": managed_files,
    }
    actions.append(_write_text(skill_path / MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", request.dry_run))
    return actions


def _sync_hook_files(platform: str, request: ImportRequest) -> list[FileAction]:
    hook_dir = _hook_dir(platform, request.scope, request.project_root, request.home_dir)
    resource_root = _resource_root() / "hooks" / platform
    actions: list[FileAction] = []
    for relative, content in _resource_files(resource_root):
        actions.append(_write_text(hook_dir / relative, content, request.dry_run))
    return actions


def _merge_hooks_config(platform: str, request: ImportRequest) -> FileAction:
    path = _hooks_config_path(platform, request.scope, request.project_root, request.home_dir)
    existing = _load_hooks_json(path)
    merged = _codex_hooks_payload(request.scope) if platform == "codex" else _cursor_hooks_payload(request.scope)
    payload = _merge_hooks_payload(existing, merged, platform)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return _write_text(path, content, request.dry_run)


def _merge_hooks_payload(existing: dict[str, Any], managed: dict[str, Any], platform: str) -> dict[str, Any]:
    result = dict(existing)
    if platform == "cursor":
        result.setdefault("version", 1)
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise HooksConfigError("hooks must be an object")
    managed_hooks = managed.get("hooks", {})
    if not isinstance(managed_hooks, dict):
        raise HooksConfigError("managed hooks must be an object")
    for event, entries in managed_hooks.items():
        current = hooks.get(event, [])
        if not isinstance(current, list):
            raise HooksConfigError(f"hooks.{event} must be an array")
        hooks[event] = [entry for entry in current if not _is_managed_hook_entry(entry)] + list(entries)
    return result


def _is_managed_hook_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    commands: list[str] = []
    if isinstance(entry.get("command"), str):
        commands.append(str(entry["command"]))
    hooks = entry.get("hooks")
    if isinstance(hooks, list):
        for item in hooks:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                commands.append(str(item["command"]))
    return any("hooks/planning-files/" in command for command in commands)


def _load_hooks_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HooksConfigError(f"invalid hooks JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise HooksConfigError(f"hooks JSON root must be an object: {path}")
    return payload


def _codex_hooks_payload(scope: str) -> dict[str, Any]:
    prefix = ".codex/hooks/planning-files" if scope == "project" else "$HOME/.codex/hooks/planning-files"
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume",
                    "hooks": [{"type": "command", "command": f"{prefix}/session-start.sh 2>/dev/null || true", "statusMessage": "Loading planning-files context"}],
                }
            ],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": f"{prefix}/user-prompt-submit.sh 2>/dev/null || true"}]}],
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": f"python3 {prefix}/pre_tool_use.py 2>/dev/null || true", "statusMessage": "Checking planning-files plan"}],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": f"python3 {prefix}/post_tool_use.py 2>/dev/null || true", "statusMessage": "Reviewing planning-files progress"}],
                }
            ],
            "Stop": [{"hooks": [{"type": "command", "command": f"python3 {prefix}/stop.py 2>/dev/null || true", "timeout": 30}]}],
        }
    }


def _cursor_hooks_payload(scope: str) -> dict[str, Any]:
    prefix = ".cursor/hooks/planning-files" if scope == "project" else "$HOME/.cursor/hooks/planning-files"
    return {
        "version": 1,
        "hooks": {
            "userPromptSubmit": [{"command": f"{prefix}/user-prompt-submit.sh", "timeout": 5}],
            "preToolUse": [{"command": f"{prefix}/pre-tool-use.sh", "matcher": "Write|Edit|Shell|Read", "timeout": 5}],
            "postToolUse": [{"command": f"{prefix}/post-tool-use.sh", "matcher": "Write|Edit", "timeout": 5}],
            "stop": [{"command": f"{prefix}/stop.sh", "timeout": 10, "loop_limit": 3}],
        },
    }


def _hook_dir(platform: str, scope: str, project_root: Path, home_dir: Path) -> Path:
    if platform == "codex":
        return (project_root / ".codex" if scope == "project" else home_dir / ".codex") / "hooks" / SKILL_NAME
    if platform == "cursor":
        return (project_root / ".cursor" if scope == "project" else home_dir / ".cursor") / "hooks" / SKILL_NAME
    raise PlanningFilesError(f"platform has no hooks: {platform}")


def _hooks_config_path(platform: str, scope: str, project_root: Path, home_dir: Path) -> Path:
    if platform == "codex":
        return (project_root / ".codex" if scope == "project" else home_dir / ".codex") / "hooks.json"
    if platform == "cursor":
        return (project_root / ".cursor" if scope == "project" else home_dir / ".cursor") / "hooks.json"
    raise PlanningFilesError(f"platform has no hooks: {platform}")


def _write_text(path: Path, content: str, dry_run: bool) -> FileAction:
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            existing = None
        action = "unchanged" if existing == content else "update"
    else:
        action = "write"
    if dry_run:
        return FileAction(path=path, action="would_write" if action != "unchanged" else "unchanged")
    if action != "unchanged":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if path.suffix in {".sh", ".py"}:
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return FileAction(path=path, action=action)


def _resource_root() -> Path:
    return Path(str(files("planning_files_skill") / "resources"))


def _resource_files(root: Path) -> list[tuple[Path, str]]:
    output: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            output.append((path.relative_to(root), path.read_text(encoding="utf-8")))
    return output


def _expand_platforms(platform: str) -> list[str]:
    normalized = platform.strip().lower()
    if normalized == "all":
        return list(SUPPORTED_PLATFORMS)
    if normalized not in SUPPORTED_PLATFORMS:
        raise PlanningFilesError(f"unsupported platform: {platform}")
    return [normalized]


def _validate_language(language: str) -> None:
    if language not in SUPPORTED_LANGUAGES:
        raise PlanningFilesError(f"unsupported language: {language}")


def _validate_scope(scope: str) -> None:
    if scope not in SUPPORTED_SCOPES:
        raise PlanningFilesError(f"unsupported scope: {scope}")
