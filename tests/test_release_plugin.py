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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _build_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    plugin_root = repo_root / "packages" / "skills-link"
    package_root = plugin_root / "src" / "skills_link"
    package_root.mkdir(parents=True, exist_ok=True)
    plugin_root.joinpath("pyproject.toml").write_text(
        '[project]\nname = "skills-link"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    package_root.joinpath("__init__.py").write_text(
        '__version__ = "0.1.0"\n',
        encoding="utf-8",
    )
    registry_payload = {
        "schema_version": 1,
        "plugins": {
            "skills-link": {
                "plugin_id": "skills-link",
                "display_name": "Skills Link",
                "description": "plugin",
                "source_type": "git",
                "package_name": "skills-link",
                "git_url": "https://example.com/repo.git",
                "subdirectory": "packages/skills-link",
                "version": "0.1.0",
                "tag": "skills-link-v0.1.0",
                "commit": "legacy-commit",
                "api_version": 1,
                "min_core_version": "0.1.0",
            }
        },
    }
    _write_json(repo_root / "registry" / "official.json", registry_payload)
    _write_json(repo_root / "src" / "agent_kit" / "official_registry.json", registry_payload)
    repo_root.joinpath("uv.lock").write_text('[[package]]\nname = "skills-link"\nversion = "0.1.0"\n', encoding="utf-8")
    return repo_root


def _git_runner(clean: bool = True, tag_exists: bool = False):
    commands: list[list[str]] = []

    def run(args: list[str], *, capture_output: bool = True, text: bool = True):
        commands.append(list(args))
        if args[:3] == ["git", "status", "--porcelain"]:
            stdout = "" if clean else " M packages/skills-link/pyproject.toml\n"
            return type("Result", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()
        if args[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return type("Result", (), {"returncode": 0, "stdout": "feature/release\n", "stderr": ""})()
        if args[:3] == ["git", "tag", "--list"]:
            stdout = f"{args[3]}\n" if tag_exists else ""
            return type("Result", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()
        if args[:2] == ["git", "add"]:
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if args[:2] == ["git", "commit"]:
            return type("Result", (), {"returncode": 0, "stdout": "[feature/release] 发布 skills-link v0.1.1\n", "stderr": ""})()
        if args[:2] == ["git", "tag"]:
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError(f"unexpected git command: {args}")

    return commands, run


def _command_runner(lock_content: str | None = None, *, fail: bool = False):
    commands: list[list[str]] = []

    def run(args: list[str], *, cwd: Path, capture_output: bool = True, text: bool = True):
        commands.append(list(args))
        if args == ["uv", "lock"]:
            if fail:
                return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "lock failed"})()
            if lock_content is not None:
                cwd.joinpath("uv.lock").write_text(lock_content, encoding="utf-8")
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError(f"unexpected command: {args}")

    return commands, run


def test_release_plugin_patch_updates_versions_registry_and_git_tag(tmp_path: Path):
    release_module = require_module("agent_kit.release_plugin")
    repo_root = _build_repo(tmp_path)
    commands, git_runner = _git_runner()
    command_calls, command_runner = _command_runner(lock_content='[[package]]\nname = "skills-link"\nversion = "0.1.1"\n')
    releaser = release_module.PluginReleaseTool(
        repo_root=repo_root,
        git_runner=git_runner,
        command_runner=command_runner,
    )

    result = releaser.release("skills-link", "patch")

    assert result.version == "0.1.1"
    assert result.tag == "skills-link-v0.1.1"
    assert result.commit_message == "发布 skills-link v0.1.1"
    assert 'version = "0.1.1"' in (repo_root / "packages" / "skills-link" / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "0.1.1"' in (
        repo_root / "packages" / "skills-link" / "src" / "skills_link" / "__init__.py"
    ).read_text(encoding="utf-8")

    for registry_path in [
        repo_root / "registry" / "official.json",
        repo_root / "src" / "agent_kit" / "official_registry.json",
    ]:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        plugin = payload["plugins"]["skills-link"]
        assert plugin["version"] == "0.1.1"
        assert plugin["tag"] == "skills-link-v0.1.1"
        assert "commit" not in plugin

    assert ["git", "commit", "-m", "发布 skills-link v0.1.1"] in commands
    assert ["git", "tag", "skills-link-v0.1.1"] in commands
    assert command_calls == [["uv", "lock"]]
    assert ["git", "add", "packages/skills-link/pyproject.toml", "packages/skills-link/src/skills_link/__init__.py", "registry/official.json", "src/agent_kit/official_registry.json", "uv.lock"] in commands


@pytest.mark.parametrize("bump, expected", [("minor", "0.2.0"), ("major", "1.0.0")])
def test_release_plugin_supports_minor_and_major_bumps(tmp_path: Path, bump: str, expected: str):
    release_module = require_module("agent_kit.release_plugin")
    repo_root = _build_repo(tmp_path)
    _, git_runner = _git_runner()
    _, command_runner = _command_runner()
    releaser = release_module.PluginReleaseTool(
        repo_root=repo_root,
        git_runner=git_runner,
        command_runner=command_runner,
    )

    result = releaser.release("skills-link", bump)

    assert result.version == expected
    assert result.tag == f"skills-link-v{expected}"


def test_release_plugin_rejects_dirty_worktree(tmp_path: Path):
    release_module = require_module("agent_kit.release_plugin")
    repo_root = _build_repo(tmp_path)
    _, git_runner = _git_runner(clean=False)
    releaser = release_module.PluginReleaseTool(repo_root=repo_root, git_runner=git_runner)

    with pytest.raises(release_module.ReleaseError, match="工作区不干净"):
        releaser.release("skills-link", "patch")


def test_release_plugin_rejects_existing_tag(tmp_path: Path):
    release_module = require_module("agent_kit.release_plugin")
    repo_root = _build_repo(tmp_path)
    _, git_runner = _git_runner(tag_exists=True)
    releaser = release_module.PluginReleaseTool(repo_root=repo_root, git_runner=git_runner)

    with pytest.raises(release_module.ReleaseError, match="tag 已存在"):
        releaser.release("skills-link", "patch")


def test_release_plugin_rejects_missing_registry_entry(tmp_path: Path):
    release_module = require_module("agent_kit.release_plugin")
    repo_root = _build_repo(tmp_path)
    registry_path = repo_root / "registry" / "official.json"
    registry_path.write_text('{"schema_version": 1, "plugins": {}}\n', encoding="utf-8")
    _, git_runner = _git_runner()
    releaser = release_module.PluginReleaseTool(repo_root=repo_root, git_runner=git_runner)

    with pytest.raises(release_module.ReleaseError, match="官方注册表中不存在插件"):
        releaser.release("skills-link", "patch")


def test_release_plugin_stops_when_uv_lock_fails(tmp_path: Path):
    release_module = require_module("agent_kit.release_plugin")
    repo_root = _build_repo(tmp_path)
    commands, git_runner = _git_runner()
    _, command_runner = _command_runner(fail=True)
    releaser = release_module.PluginReleaseTool(
        repo_root=repo_root,
        git_runner=git_runner,
        command_runner=command_runner,
    )

    with pytest.raises(release_module.ReleaseError, match="uv lock 执行失败"):
        releaser.release("skills-link", "patch")

    assert ["git", "commit", "-m", "发布 skills-link v0.1.1"] not in commands
