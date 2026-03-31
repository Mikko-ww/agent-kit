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


def test_add_rule_chinese_no_false_duplicate(tmp_path: Path):
    """中文规则不应因 fingerprint 退化为空而误报重复。"""
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "规则一", "--statement", "始终使用中文注释", "--rationale", "统一风格",
         "--domain", "代码风格"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "规则二", "--statement", "始终使用类型注解", "--rationale", "提高可读性",
         "--domain", "代码风格"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Warning" not in result.stderr


def test_retire_rule_corrupt_json(tmp_path: Path):
    """retire_rule 遇到损坏 JSON 应报错而非崩溃。"""
    scripts_dir = _setup_scripts(tmp_path)
    rules_dir = tmp_path / ".agents" / "self-evolve" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "R-001.json").write_text("not valid json", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "retire_rule.py"), "R-001"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "Failed" in result.stderr


def test_edit_rule_corrupt_json(tmp_path: Path):
    """edit_rule 遇到损坏 JSON 应报错而非崩溃。"""
    scripts_dir = _setup_scripts(tmp_path)
    rules_dir = tmp_path / ".agents" / "self-evolve" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "R-001.json").write_text("{invalid", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "edit_rule.py"), "R-001", "--title", "New"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "Failed" in result.stderr


def test_add_rule_empty_title(tmp_path: Path):
    """add_rule 应拒绝空标题。"""
    scripts_dir = _setup_scripts(tmp_path)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "   ", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "title cannot be empty" in result.stderr


def test_add_rule_empty_statement(tmp_path: Path):
    """add_rule 应拒绝空语句。"""
    scripts_dir = _setup_scripts(tmp_path)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "  ", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "statement cannot be empty" in result.stderr


def test_add_rule_empty_rationale(tmp_path: Path):
    """add_rule 应拒绝空理由。"""
    scripts_dir = _setup_scripts(tmp_path)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "S", "--rationale", "", "--domain", "d"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "rationale cannot be empty" in result.stderr


def test_add_rule_empty_domain(tmp_path: Path):
    """add_rule 应拒绝空域。"""
    scripts_dir = _setup_scripts(tmp_path)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "S", "--rationale", "R", "--domain", " "],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "domain cannot be empty" in result.stderr


def test_edit_rule_empty_title(tmp_path: Path):
    """edit_rule 应拒绝空标题。"""
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "Old", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "edit_rule.py"), "R-001", "--title", "  "],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "title cannot be empty" in result.stderr


def test_edit_rule_empty_statement(tmp_path: Path):
    """edit_rule 应拒绝空语句。"""
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "edit_rule.py"), "R-001", "--statement", ""],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "statement cannot be empty" in result.stderr


def test_edit_rule_write_error_handling(tmp_path: Path):
    """edit_rule 应能处理写入错误。"""
    scripts_dir = _setup_scripts(tmp_path)
    subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    # 将规则文件设为只读以触发写入错误
    rule_file = tmp_path / ".agents" / "self-evolve" / "rules" / "R-001.json"
    rule_file.chmod(0o444)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "edit_rule.py"), "R-001", "--title", "New"],
        capture_output=True, text=True,
    )
    # 恢复权限以便清理
    rule_file.chmod(0o644)
    assert result.returncode != 0
    assert "Failed to write" in result.stderr


def test_add_rule_write_error_handling(tmp_path: Path):
    """add_rule 应能处理写入错误。"""
    scripts_dir = _setup_scripts(tmp_path)
    rules_dir = tmp_path / ".agents" / "self-evolve" / "rules"
    rules_dir.mkdir(parents=True)
    # 将规则目录设为只读以触发写入错误
    rules_dir.chmod(0o555)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "add_rule.py"),
         "--title", "T", "--statement", "S", "--rationale", "R", "--domain", "d"],
        capture_output=True, text=True,
    )
    # 恢复权限以便清理
    rules_dir.chmod(0o755)
    assert result.returncode != 0
    assert "Failed to write" in result.stderr
