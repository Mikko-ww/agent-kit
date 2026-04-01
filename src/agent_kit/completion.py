from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

MANAGED_COMPLETION_MARKER = "# agent-kit managed completion"
COMPLETION_SCRIPT_VERSION = "1.0.0"


class SupportedShell(str, Enum):
    """支持的 Shell 类型。"""
    ZSH = "zsh"
    # 未来可扩展: BASH = "bash", FISH = "fish"


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
        f"{MANAGED_COMPLETION_MARKER} v{COMPLETION_SCRIPT_VERSION}",
        "",
        '_agent-kit() {',
        '    local completions',
        '    completions=$(COMP_WORDS="${words[*]}" \\',
        '                  COMP_CWORD=$((CURRENT-1)) \\',
        '                  _AGENT_KIT_COMPLETE=zsh_complete \\',
        '                  agent-kit 2>/dev/null)',
        '    if [[ $? -eq 0 && -n "$completions" ]]; then',
        '        eval "$completions"',
        '    fi',
        '}',
        "",
        "compdef _agent-kit agent-kit",
        "compdef _agent-kit ak",
        "",
    ])


def generate_omz_plugin_zsh() -> str:
    """生成 oh-my-zsh 插件入口文件内容。"""
    return "\n".join([
        f"{MANAGED_COMPLETION_MARKER} plugin v{COMPLETION_SCRIPT_VERSION}",
        "#",
        "# This file is managed by agent-kit. Do not edit manually.",
        "# To regenerate: agent-kit completion install",
        "#",
        "# Add plugin directory to fpath for completion discovery",
        "fpath=(${0:A:h} $fpath)",
        "",
        "# Register completions for agent-kit and ak alias",
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
    plugin_zsh = plugin_dir / "agent-kit.plugin.zsh"

    comp_content = generate_zsh_completion_script()
    plugin_content = generate_omz_plugin_zsh()

    changed = False
    if not comp_file.exists() or comp_file.read_text(encoding="utf-8") != comp_content:
        comp_file.write_text(comp_content, encoding="utf-8")
        changed = True
    if not plugin_zsh.exists() or plugin_zsh.read_text(encoding="utf-8") != plugin_content:
        plugin_zsh.write_text(plugin_content, encoding="utf-8")
        changed = True

    return CompletionInstallResult(method="omz", path=comp_file, changed=changed)


def _install_zfunc(home: Path) -> CompletionInstallResult:
    zfunc_dir = home / ".zfunc"
    zfunc_dir.mkdir(parents=True, exist_ok=True)
    comp_file = zfunc_dir / "_agent-kit"

    comp_content = generate_zsh_completion_script()
    changed = False
    if not comp_file.exists() or comp_file.read_text(encoding="utf-8") != comp_content:
        comp_file.write_text(comp_content, encoding="utf-8")
        changed = True

    return CompletionInstallResult(method="zfunc", path=comp_file, changed=changed)


def _is_managed_installation(comp_file: Path) -> bool:
    """检查补全文件是否包含 managed marker。"""
    if not comp_file.exists():
        return False
    try:
        content = comp_file.read_text(encoding="utf-8")
        return MANAGED_COMPLETION_MARKER in content
    except Exception:
        return False


def remove_zsh_completion(home: Path | None = None) -> CompletionRemoveResult:
    """卸载已安装的 Zsh 补全脚本。同时检查 oh-my-zsh 和 zfunc 两个位置。"""
    home = home or Path.home()
    removed_paths = []

    # 检查 oh-my-zsh 安装
    omz_custom = detect_omz_custom_dir(home=home)
    if omz_custom is not None:
        plugin_dir = omz_custom / "plugins" / "agent-kit"
        comp_file = plugin_dir / "_agent-kit"
        if plugin_dir.exists() and _is_managed_installation(comp_file):
            shutil.rmtree(plugin_dir)
            removed_paths.append(plugin_dir)

    # 检查 zfunc 安装
    zfunc_file = home / ".zfunc" / "_agent-kit"
    if zfunc_file.exists() and _is_managed_installation(zfunc_file):
        zfunc_file.unlink()
        removed_paths.append(zfunc_file)

    if removed_paths:
        return CompletionRemoveResult(removed=True, path=removed_paths[0])
    return CompletionRemoveResult(removed=False, path=None)
