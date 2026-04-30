from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_shell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_dev_env_script_exposes_workspace_plugin_commands() -> None:
    result = run_shell(
        """
        source scripts/dev/dev-env.sh >/dev/null
        ak skills-link --plugin-metadata
        ak opencode-env-switch --plugin-metadata
        ak planning-files-skill --plugin-metadata
        """
    )

    assert result.returncode == 0, result.stderr or result.stdout

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 3
    assert json.loads(lines[0])["plugin_id"] == "skills-link"
    assert json.loads(lines[1])["plugin_id"] == "opencode-env-switch"
    assert json.loads(lines[2])["plugin_id"] == "planning-files-skill"
