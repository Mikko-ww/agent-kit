from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def test_generic_project_import_writes_zh_skill_and_manifest(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()

    result = logic.import_platform(
        logic.ImportRequest(
            platform="generic",
            language="zh-CN",
            scope="project",
            project_root=project_root,
            home_dir=home_dir,
        )
    )

    skill_dir = project_root / ".agents" / "skills" / "planning-files"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    manifest = json.loads((skill_dir / ".planning-files-skill.json").read_text(encoding="utf-8"))

    assert result.changed is True
    assert "name: planning-files" in skill_text
    assert "# 文件规划系统" in skill_text
    assert (skill_dir / "templates" / "task_plan.md").exists()
    assert manifest["plugin_id"] == "planning-files-skill"
    assert manifest["skill_name"] == "planning-files"
    assert manifest["platform"] == "generic"
    assert manifest["language"] == "zh-CN"
    assert "SKILL.md" in manifest["managed_files"]


def test_opencode_global_import_uses_opencode_home_path(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()

    logic.import_platform(
        logic.ImportRequest(
            platform="opencode",
            language="en",
            scope="global",
            project_root=project_root,
            home_dir=home_dir,
        )
    )

    skill_dir = home_dir / ".config" / "opencode" / "skills" / "planning-files"
    assert (skill_dir / "SKILL.md").exists()
    assert "name: planning-files" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_dry_run_reports_changes_without_writing_files(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()

    result = logic.import_platform(
        logic.ImportRequest(
            platform="generic",
            language="en",
            scope="project",
            project_root=project_root,
            home_dir=home_dir,
            dry_run=True,
        )
    )

    assert result.changed is True
    assert any(action.action == "would_write" for action in result.actions)
    assert not (project_root / ".agents" / "skills" / "planning-files").exists()


def test_repeat_import_is_idempotent_and_language_can_be_replaced(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()
    request = logic.ImportRequest(
        platform="generic",
        language="zh-CN",
        scope="project",
        project_root=project_root,
        home_dir=home_dir,
    )

    first = logic.import_platform(request)
    second = logic.import_platform(request)
    switched = logic.import_platform(logic.ImportRequest(**{**request.__dict__, "language": "en"}))

    skill_dir = project_root / ".agents" / "skills" / "planning-files"
    manifest = json.loads((skill_dir / ".planning-files-skill.json").read_text(encoding="utf-8"))

    assert first.changed is True
    assert second.changed is False
    assert switched.changed is True
    assert manifest["language"] == "en"
    assert "# Planning Files" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_existing_unmanaged_skill_requires_force(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()
    skill_dir = project_root / ".agents" / "skills" / "planning-files"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# user skill\n", encoding="utf-8")

    request = logic.ImportRequest(
        platform="generic",
        language="en",
        scope="project",
        project_root=project_root,
        home_dir=home_dir,
    )
    with pytest.raises(logic.ResourceConflict):
        logic.import_platform(request)

    result = logic.import_platform(logic.ImportRequest(**{**request.__dict__, "force": True}))

    assert result.changed is True
    assert "name: planning-files" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_codex_project_import_merges_hooks_and_keeps_existing_entries(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()
    hooks_path = project_root / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "echo keep-existing",
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    logic.import_platform(
        logic.ImportRequest(
            platform="codex",
            language="en",
            scope="project",
            project_root=project_root,
            home_dir=home_dir,
        )
    )

    payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    stop_commands = [
        hook["command"]
        for entry in payload["hooks"]["Stop"]
        for hook in entry.get("hooks", [])
    ]

    assert "echo keep-existing" in stop_commands
    assert any(".codex/hooks/planning-files/stop.py" in command for command in stop_commands)
    assert (project_root / ".codex" / "hooks" / "planning-files" / "stop.py").exists()
    assert (project_root / ".codex" / "hooks" / "planning-files" / "session-start.sh").read_text(
        encoding="utf-8"
    ).startswith("#!/usr/bin/env bash")


def test_cursor_project_import_updates_managed_hooks_and_keeps_user_hooks(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()
    hooks_path = project_root / ".cursor" / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {
                    "stop": [
                        {"command": "echo keep-existing", "timeout": 1},
                        {"command": ".cursor/hooks/planning-files/old-stop.sh", "timeout": 1},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    logic.import_platform(
        logic.ImportRequest(
            platform="cursor",
            language="en",
            scope="project",
            project_root=project_root,
            home_dir=home_dir,
        )
    )

    payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    stop_commands = [entry["command"] for entry in payload["hooks"]["stop"]]

    assert "echo keep-existing" in stop_commands
    assert ".cursor/hooks/planning-files/old-stop.sh" not in stop_commands
    assert ".cursor/hooks/planning-files/stop.sh" in stop_commands
    assert (project_root / ".cursor" / "hooks" / "planning-files" / "stop.sh").exists()


def test_invalid_hooks_json_raises_clear_error(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()
    hooks_path = project_root / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(logic.HooksConfigError, match="invalid hooks JSON"):
        logic.import_platform(
            logic.ImportRequest(
                platform="codex",
                language="en",
                scope="project",
                project_root=project_root,
                home_dir=home_dir,
            )
        )


def test_hooks_event_shape_conflict_raises_clear_error(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()
    hooks_path = project_root / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(json.dumps({"hooks": {"Stop": {"command": "echo wrong-shape"}}}), encoding="utf-8")

    with pytest.raises(logic.HooksConfigError, match=r"hooks\.Stop must be an array"):
        logic.import_platform(
            logic.ImportRequest(
                platform="codex",
                language="en",
                scope="project",
                project_root=project_root,
                home_dir=home_dir,
            )
        )


def test_status_reports_installed_language(tmp_path: Path):
    logic = require_module("planning_files_skill.logic")
    project_root = tmp_path / "repo"
    home_dir = tmp_path / "home"
    project_root.mkdir()
    home_dir.mkdir()

    missing = logic.inspect_platform(
        platform="generic",
        scope="project",
        project_root=project_root,
        home_dir=home_dir,
    )
    logic.import_platform(
        logic.ImportRequest(
            platform="generic",
            language="zh-CN",
            scope="project",
            project_root=project_root,
            home_dir=home_dir,
        )
    )
    installed = logic.inspect_platform(
        platform="generic",
        scope="project",
        project_root=project_root,
        home_dir=home_dir,
    )

    assert missing.installed is False
    assert installed.installed is True
    assert installed.language == "zh-CN"
