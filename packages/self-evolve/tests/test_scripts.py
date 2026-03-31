import json
import subprocess
import sys
from pathlib import Path


def _setup_scripts(tmp_path: Path) -> Path:
    """将脚本复制到 tmp_path 下模拟项目结构"""
    scripts_dir = tmp_path / ".agents" / "skills" / "self-evolve" / "scripts"
    scripts_dir.mkdir(parents=True)
    src_scripts = Path(__file__).resolve().parent.parent / "src" / "self_evolve" / "scripts"
    for f in src_scripts.glob("*.py"):
        (scripts_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    return scripts_dir


def test_add_rule_creates_json_file(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "Test rule",
         "--statement", "Always test before commit.",
         "--rationale", "Prevents regressions.",
         "--domain", "testing",
         "--tag", "ci"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "R-001" in result.stdout
    rule_file = tmp_path / ".agents" / "self-evolve" / "rules" / "R-001.json"
    assert rule_file.exists()
    data = json.loads(rule_file.read_text(encoding="utf-8"))
    assert data["title"] == "Test rule"
    assert data["status"] == "active"


def test_add_rule_warns_on_duplicate(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "Always test.", "--rationale", "R", "--domain", "testing"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T2", "--statement", "Always test.", "--rationale", "R2", "--domain", "testing"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Warning" in result.stderr


def test_retire_rule(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "retire_rule.py"), "R-001"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(
        (tmp_path / ".agents" / "self-evolve" / "rules" / "R-001.json").read_text(encoding="utf-8")
    )
    assert data["status"] == "retired"


def test_edit_rule(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "Old", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "edit_rule.py"), "R-001", "--title", "New"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(
        (tmp_path / ".agents" / "self-evolve" / "rules" / "R-001.json").read_text(encoding="utf-8")
    )
    assert data["title"] == "New"


def test_list_rules(tmp_path: Path):
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "Test rule", "--statement", "S", "--rationale", "R", "--domain", "testing"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "list_rules.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "R-001" in result.stdout
