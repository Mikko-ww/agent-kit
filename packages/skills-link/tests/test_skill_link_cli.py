from __future__ import annotations

import importlib
import logging
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def write_skill(base: Path, name: str) -> Path:
    skill_dir = base / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return skill_dir


class FakeIO:
    def __init__(self, *, text_answers=(), confirm_answers=(), multi_answers=()):
        self._text_answers = deque(text_answers)
        self._confirm_answers = deque(confirm_answers)
        self._multi_answers = deque(multi_answers)

    def echo(self, message: str) -> None:
        typer.echo(message)

    def warn(self, message: str) -> None:
        typer.echo(message)

    def error(self, message: str) -> None:
        typer.echo(message)

    def prompt_text(self, message: str, default: str | None = None) -> str:
        if self._text_answers:
            return self._text_answers.popleft()
        if default is not None:
            return default
        raise AssertionError(f"missing text answer for: {message}")

    def confirm(self, message: str, default: bool = False) -> bool:
        if self._confirm_answers:
            return self._confirm_answers.popleft()
        return default

    def select_many(self, message: str, choices):
        if self._multi_answers:
            return list(self._multi_answers.popleft())
        return []


def build_app(tmp_path: Path, io: FakeIO):
    plugin_cli = require_module("skills_link.plugin_cli")
    runtime = SimpleNamespace(
        logger=logging.getLogger("skills-link-test"),
        cwd=tmp_path,
        config_root=tmp_path / "config",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
        io=io,
    )
    return plugin_cli.build_app(runtime_factory=lambda: runtime)


def save_config(tmp_path: Path, source_dir: Path, targets: list[tuple[str, Path]]):
    config_module = require_module("skills_link.config")
    config_module.save_config(
        tmp_path / "config",
        config_module.SkillLinkConfig(
            source_dir=source_dir,
            targets=[
                config_module.TargetConfig(name=name, path=path)
                for name, path in targets
            ],
        ),
    )


def test_plugin_metadata_output():
    plugin_cli = require_module("skills_link.plugin_cli")
    result = CliRunner().invoke(plugin_cli.build_app(), ["--plugin-metadata"])

    assert result.exit_code == 0
    assert '"plugin_id": "skills-link"' in result.output
    assert '"config_version": 2' in result.output


def test_list_auto_runs_init_when_not_configured_and_writes_multi_target_config(tmp_path: Path):
    source_dir = tmp_path / "skills"
    target_dir = tmp_path / "codex"
    source_dir.mkdir()
    write_skill(source_dir, "alpha")
    io = FakeIO(
        text_answers=[str(source_dir), "codex", str(target_dir)],
        confirm_answers=[True],
    )
    app = build_app(tmp_path, io)

    result = CliRunner().invoke(app, ["list"])

    assert result.exit_code == 0
    assert "alpha [not_linked]" in result.output
    config_path = tmp_path / "config" / "plugins" / "skills-link" / "config.jsonc"
    assert config_path.exists()
    assert '"config_version": 2' in config_path.read_text(encoding="utf-8")
    assert '"name": "codex"' in config_path.read_text(encoding="utf-8")
    assert target_dir.exists()


def test_list_auto_runs_init_when_paths_are_wrapped_in_quotes(tmp_path: Path):
    source_dir = tmp_path / "skills"
    target_dir = tmp_path / "codex"
    source_dir.mkdir()
    write_skill(source_dir, "alpha")
    io = FakeIO(
        text_answers=[f'"{source_dir}"', "codex", f"'{target_dir}'"],
        confirm_answers=[True],
    )
    app = build_app(tmp_path, io)

    result = CliRunner().invoke(app, ["list"])

    assert result.exit_code == 0
    assert "alpha [not_linked]" in result.output
    assert target_dir.exists()


def test_link_status_and_unlink_commands_support_multiple_targets(tmp_path: Path):
    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    source_dir.mkdir()
    codex_dir.mkdir()
    claude_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    beta = write_skill(source_dir, "beta")
    (codex_dir / "beta").mkdir()
    save_config(
        tmp_path,
        source_dir,
        [("codex", codex_dir), ("claude", claude_dir)],
    )
    io = FakeIO(multi_answers=[["alpha", "beta"], ["alpha"]])
    app = build_app(tmp_path, io)
    runner = CliRunner()

    link_result = runner.invoke(app, ["link"])

    assert link_result.exit_code == 1
    assert "linked alpha -> codex" in link_result.output
    assert "linked alpha -> claude" in link_result.output
    assert "linked beta -> claude" in link_result.output
    assert "conflict beta -> codex; resolve it manually" in link_result.output
    assert (codex_dir / "alpha").is_symlink()
    assert (codex_dir / "alpha").resolve() == alpha.resolve()
    assert (claude_dir / "alpha").is_symlink()
    assert (claude_dir / "alpha").resolve() == alpha.resolve()
    assert (claude_dir / "beta").is_symlink()
    assert (claude_dir / "beta").resolve() == beta.resolve()

    status_result = runner.invoke(app, ["status"])

    assert status_result.exit_code == 0
    assert "targets: 2" in status_result.output
    assert "[codex]" in status_result.output
    assert "[claude]" in status_result.output
    assert "linked: 1" in status_result.output
    assert "conflict: 1" in status_result.output

    unlink_result = runner.invoke(app, ["unlink"])

    assert unlink_result.exit_code == 0
    assert "unlinked alpha -> codex" in unlink_result.output
    assert "unlinked alpha -> claude" in unlink_result.output
    assert not (codex_dir / "alpha").exists()
    assert not (claude_dir / "alpha").exists()


def test_list_supports_target_filter_and_errors_for_unknown_target(tmp_path: Path):
    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    source_dir.mkdir()
    codex_dir.mkdir()
    claude_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    (codex_dir / "alpha").symlink_to(alpha, target_is_directory=True)
    save_config(
        tmp_path,
        source_dir,
        [("codex", codex_dir), ("claude", claude_dir)],
    )
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    filtered = runner.invoke(app, ["list", "--target", "codex"])

    assert filtered.exit_code == 0
    assert "alpha [linked]" in filtered.output
    assert "claude" not in filtered.output

    unknown = runner.invoke(app, ["list", "--target", "missing"])

    assert unknown.exit_code == 1
    assert "unknown target(s): missing" in unknown.output


def test_target_add_update_list_and_remove_commands_manage_registry(tmp_path: Path):
    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    claude_dir = tmp_path / "claude"
    source_dir.mkdir()
    codex_dir.mkdir()
    write_skill(source_dir, "alpha")
    save_config(tmp_path, source_dir, [("codex", codex_dir)])
    io = FakeIO(confirm_answers=[True])
    app = build_app(tmp_path, io)
    runner = CliRunner()

    add_result = runner.invoke(
        app,
        ["target", "add", "--name", "claude", "--path", str(claude_dir)],
    )
    assert add_result.exit_code == 0

    list_result = runner.invoke(app, ["target", "list"])
    assert list_result.exit_code == 0
    assert "[codex]" in list_result.output
    assert "[claude]" in list_result.output

    update_result = runner.invoke(
        app,
        ["target", "update", "--name", "claude", "--new-name", "anthropic"],
    )
    assert update_result.exit_code == 0

    remove_result = runner.invoke(app, ["target", "remove", "--name", "anthropic"])
    assert remove_result.exit_code == 0

    config_module = require_module("skills_link.config")
    loaded = config_module.load_config(tmp_path / "config")
    assert loaded is not None
    assert [target.name for target in loaded.targets] == ["codex"]


def test_target_update_path_and_remove_reject_when_managed_links_exist(tmp_path: Path):
    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    next_dir = tmp_path / "next"
    source_dir.mkdir()
    codex_dir.mkdir()
    alpha = write_skill(source_dir, "alpha")
    (codex_dir / "alpha").symlink_to(alpha, target_is_directory=True)
    save_config(tmp_path, source_dir, [("codex", codex_dir)])
    app = build_app(tmp_path, FakeIO())
    runner = CliRunner()

    update_result = runner.invoke(
        app,
        ["target", "update", "--name", "codex", "--path", str(next_dir)],
    )
    assert update_result.exit_code == 1
    assert "unlink --target codex" in update_result.output

    remove_result = runner.invoke(app, ["target", "remove", "--name", "codex"])
    assert remove_result.exit_code == 1
    assert "unlink --target codex" in remove_result.output


def test_target_add_rejects_duplicate_name(tmp_path: Path):
    source_dir = tmp_path / "skills"
    codex_dir = tmp_path / "codex"
    other_dir = tmp_path / "other"
    source_dir.mkdir()
    codex_dir.mkdir()
    other_dir.mkdir()
    write_skill(source_dir, "alpha")
    save_config(tmp_path, source_dir, [("codex", codex_dir)])
    app = build_app(tmp_path, FakeIO())

    result = CliRunner().invoke(
        app,
        ["target", "add", "--name", "codex", "--path", str(other_dir)],
    )

    assert result.exit_code == 1
    assert "duplicate target name: codex" in result.output
