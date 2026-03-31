from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

MANAGED_COMPLETION_MARKER = "# agent-kit managed completion"


def detect_omz_custom_dir(home: Path | None = None) -> Path | None:
    """检测 oh-my-zsh 自定义插件目录。

    优先级：
    1. ZSH_CUSTOM 环境变量
    2. ~/.oh-my-zsh/custom 默认路径
    """
    env_val = os.environ.get("ZSH_CUSTOM")
    if env_val:
        p = Path(env_val)
        if p.is_dir():
            return p
    home = home or Path.home()
    default = home / ".oh-my-zsh" / "custom"
    if default.is_dir():
        return default
    return None


def generate_zsh_completion_script() -> str:
    """生成 Zsh 补全脚本内容，底层调用 Typer/Click 的补全机制。"""
    return "\n".join([
        "#compdef agent-kit ak",
        "",
        MANAGED_COMPLETION_MARKER,
        "",
        '_agent-kit() {',
        '    eval "$(COMP_WORDS="${words[*]}" \\',
        '            COMP_CWORD=$((CURRENT-1)) \\',
        '            _AGENT_KIT_COMPLETE=zsh_complete \\',
        '            agent-kit)"',
        '}',
        "",
        "compdef _agent-kit agent-kit",
        "compdef _agent-kit ak",
        "",
    ])


def generate_omz_plugin_zsh() -> str:
    """生成 oh-my-zsh 插件入口文件内容。"""
    return "\n".join([
        MANAGED_COMPLETION_MARKER + " plugin",
        "fpath=(${0:A:h} $fpath)",
        "compdef _agent-kit agent-kit",
        "compdef _agent-kit ak",
        "",
    ])


@dataclass(slots=True, frozen=True)
class CompletionInstallResult:
    method: str           # "omz" | "zfunc"
    path: Path            # 主补全脚本路径
    changed: bool         # 是否实际写入了文件


@dataclass(slots=True, frozen=True)
class CompletionRemoveResult:
    removed: bool         # 是否实际删除了文件
    path: Path | None     # 被删除的路径


def install_zsh_completion(home: Path | None = None) -> CompletionInstallResult:
    """安装 Zsh 补全脚本。优先 oh-my-zsh 路径，否则使用 ~/.zfunc。"""
    home = home or Path.home()
    omz_custom = detect_omz_custom_dir(home=home)
    if omz_custom is not None:
        return _install_omz(omz_custom)
    return _install_zfunc(home)


def _install_omz(custom_dir: Path) -> CompletionInstallResult:
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    comp_file = plugin_dir / "_agent-kit"
    comp_file.write_text(generate_zsh_completion_script(), encoding="utf-8")
    plugin_zsh = plugin_dir / "agent-kit.plugin.zsh"
    plugin_zsh.write_text(generate_omz_plugin_zsh(), encoding="utf-8")
    return CompletionInstallResult(method="omz", path=comp_file, changed=True)


def _install_zfunc(home: Path) -> CompletionInstallResult:
    zfunc_dir = home / ".zfunc"
    zfunc_dir.mkdir(parents=True, exist_ok=True)
    comp_file = zfunc_dir / "_agent-kit"
    comp_file.write_text(generate_zsh_completion_script(), encoding="utf-8")
    return CompletionInstallResult(method="zfunc", path=comp_file, changed=True)


def remove_zsh_completion(home: Path | None = None) -> CompletionRemoveResult:
    """卸载已安装的 Zsh 补全脚本。"""
    home = home or Path.home()
    omz_custom = detect_omz_custom_dir(home=home)
    if omz_custom is not None:
        plugin_dir = omz_custom / "plugins" / "agent-kit"
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
            return CompletionRemoveResult(removed=True, path=plugin_dir)
    zfunc_file = home / ".zfunc" / "_agent-kit"
    if zfunc_file.exists():
        zfunc_file.unlink()
        return CompletionRemoveResult(removed=True, path=zfunc_file)
    return CompletionRemoveResult(removed=False, path=None)
