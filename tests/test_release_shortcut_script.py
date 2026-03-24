from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_repo(tmp_path: Path) -> Path:
    source_script = REPO_ROOT / "scripts" / "release" / "ak-release.sh"
    if not source_script.exists():  # pragma: no cover - red phase
        pytest.fail(f"missing script under test: {source_script}")

    repo_root = tmp_path / "repo"
    (repo_root / "scripts" / "release").mkdir(parents=True, exist_ok=True)
    (repo_root / "registry").mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_script, repo_root / "scripts" / "release" / "ak-release.sh")
    (repo_root / "scripts" / "release" / "release_plugin.py").write_text(
        "import sys\nprint('release:' + ' '.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    (repo_root / "registry" / "official.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "plugins": {
                    "skills-link": {"plugin_id": "skills-link"},
                    "opencode-env-switch": {"plugin_id": "opencode-env-switch"},
                },
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return repo_root


def _run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/release/ak-release.sh", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )


def test_release_shortcut_passes_through_to_release_script(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)

    result = _run(repo_root, "skills-link", "patch")

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "release:skills-link patch"


def test_release_shortcut_without_args_shows_usage_and_available_plugins(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)

    result = _run(repo_root)

    assert result.returncode == 1
    assert "用法" in result.stderr
    assert "skills-link" in result.stderr
    assert "opencode-env-switch" in result.stderr
    assert "patch" in result.stderr
    assert "minor" in result.stderr
    assert "major" in result.stderr


def test_release_shortcut_requires_bump_after_plugin_id(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)

    result = _run(repo_root, "skills-link")

    assert result.returncode == 1
    assert "还需要提供版本类型" in result.stderr
    assert "patch" in result.stderr
    assert "minor" in result.stderr
    assert "major" in result.stderr


def test_release_shortcut_rejects_unknown_plugin_id(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)

    result = _run(repo_root, "unknown-plugin", "patch")

    assert result.returncode == 1
    assert "插件无效" in result.stderr
    assert "skills-link" in result.stderr
    assert "opencode-env-switch" in result.stderr


def test_release_shortcut_rejects_unknown_bump_type(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)

    result = _run(repo_root, "skills-link", "foo")

    assert result.returncode == 1
    assert "版本类型无效" in result.stderr
    assert "patch" in result.stderr
    assert "minor" in result.stderr
    assert "major" in result.stderr


def test_release_shortcut_help_uses_usage_output(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)

    result = _run(repo_root, "--help")

    assert result.returncode == 0
    assert "用法" in result.stdout
    assert "skills-link" in result.stdout
