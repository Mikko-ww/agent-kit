from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def require_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - used for red phase
        pytest.fail(f"could not import {name}: {exc}")


def write_global_config(path: Path, *, language: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{\n  "language": "%s"\n}\n' % language, encoding="utf-8")


def test_resolve_language_prefers_env_over_config_and_system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    locale_module = require_module("agent_kit.locale")
    config_path = tmp_path / "config.jsonc"
    write_global_config(config_path, language="zh-CN")
    monkeypatch.setenv("AGENT_KIT_LANG", "en")
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")

    resolved = locale_module.resolve_language(config_path=config_path)

    assert resolved.code == "en"
    assert resolved.source == "env"


def test_resolve_language_uses_config_when_env_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    locale_module = require_module("agent_kit.locale")
    config_path = tmp_path / "config.jsonc"
    write_global_config(config_path, language="zh-CN")
    monkeypatch.delenv("AGENT_KIT_LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")

    resolved = locale_module.resolve_language(config_path=config_path)

    assert resolved.code == "zh-CN"
    assert resolved.source == "config"


def test_resolve_language_normalizes_supported_system_locales(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    locale_module = require_module("agent_kit.locale")
    monkeypatch.delenv("AGENT_KIT_LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.setenv("LC_MESSAGES", "zh_Hans_CN.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")

    resolved = locale_module.resolve_language(config_path=tmp_path / "missing.jsonc")

    assert resolved.code == "zh-CN"
    assert resolved.source == "system"


def test_resolve_language_falls_back_to_english_for_unsupported_locale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    locale_module = require_module("agent_kit.locale")
    monkeypatch.delenv("AGENT_KIT_LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "ja_JP.UTF-8")

    resolved = locale_module.resolve_language(config_path=tmp_path / "missing.jsonc")

    assert resolved.code == "en"
    assert resolved.source == "default"
