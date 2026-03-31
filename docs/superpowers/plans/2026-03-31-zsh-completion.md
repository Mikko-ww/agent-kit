# Zsh 命令补全功能 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `agent-kit` 实现 Zsh 命令补全功能（方案三：混合方案），启用 Typer/Click 内置补全引擎，新增 `completion` 子命令组管理补全安装，同时覆盖 `agent-kit` 和 `ak` 别名的补全。

**Architecture:** 采用混合方案，结合 Typer/Click 内置动态补全能力和 oh-my-zsh 插件分发形式。底层使用 Typer/Click 的补全运行时作为数据源，上层提供 `completion install/show/remove` 子命令管理安装。安装时自动检测 oh-my-zsh 环境并选择对应路径，同时在补全脚本中自动注册 `ak` 别名补全。

**Tech Stack:** Python 3.11+, Typer, Click, pytest, Zsh completion system

**参考设计文档：** `docs/superpowers/specs/2026-03-31-zsh-completion-design.md`

---

## Chunk 1: 启用补全引擎

### Task 1: 为补全引擎启用写红测

**Files:**
- Modify: `tests/test_core_cli.py`

- [ ] **Step 1: 写失败测试，验证 Typer 内置补全已启用**

在 `tests/test_core_cli.py` 中新增测试，确认主 app 和所有子命令组都没有禁用补全：

```python
def test_app_has_completion_enabled():
    """Typer 内置补全引擎应被启用（不再有 add_completion=False）。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    # Typer 在启用补全时会注册内部补全回调
    # 确认源码中不再包含 add_completion=False
    source = Path("src/agent_kit/cli.py").read_text(encoding="utf-8")
    assert "add_completion=False" not in source
```

- [ ] **Step 2: 写失败测试，验证 Typer 默认的 `--install-completion` 和 `--show-completion` 被隐藏**

```python
def test_typer_default_completion_options_are_hidden():
    """Typer 默认注入的 --install-completion 和 --show-completion 应被隐藏，
    由自定义 completion 子命令代替。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--install-completion" not in result.output
    assert "--show-completion" not in result.output
```

- [ ] **Step 3: 运行精确测试确认先失败**

Run: `uv run pytest tests/test_core_cli.py -k "completion_enabled or completion_options" -v`
Expected: FAIL，因为 `add_completion=False` 仍存在

### Task 2: 启用 Typer/Click 内置补全引擎

**Files:**
- Modify: `src/agent_kit/cli.py`

- [ ] **Step 1: 移除所有 `add_completion=False`**

移除以下 4 处 `add_completion=False`：

```python
# 行 43：主应用
app = typer.Typer(
    ...,
    add_completion=False,   # 移除此行
)

# 行 60：plugins 子命令组
plugins_app = typer.Typer(..., add_completion=False)  # 移除 add_completion=False

# 行 61：config 子命令组
config_app = typer.Typer(..., add_completion=False)   # 移除 add_completion=False

# 行 62：alias 子命令组
alias_app = typer.Typer(..., add_completion=False)    # 移除 add_completion=False
```

- [ ] **Step 2: 隐藏 Typer 默认注入的补全选项**

在 `app` 的 `@app.callback()` 中，或者在创建 `app` 后，通过 Click 底层 API 隐藏默认的 `--install-completion` 和 `--show-completion`，确保这两个选项不出现在 `--help` 输出中，由后续自定义的 `completion` 子命令组替代：

```python
# 在 create_app() 中创建 app 后，修改回调参数的 hidden 属性
# 或者在 callback 定义中覆盖这些参数
```

具体实现可以在 app 创建后遍历 `app.registered_callback` 或使用 Typer 的 `rich_help_panel` 隐藏，也可以通过重写 callback 参数为 hidden 来实现。

- [ ] **Step 3: 运行测试确认转绿**

Run: `uv run pytest tests/test_core_cli.py -k "completion_enabled or completion_options" -v`
Expected: PASS

- [ ] **Step 4: 验证 Typer/Click 补全引擎能工作**

Run:

```bash
_AGENT_KIT_COMPLETE=zsh_source uv run agent-kit 2>/dev/null | head -5
```

Expected: 输出包含 Zsh 补全脚本片段（如 `_agent-kit_completion` 或 `compdef`）

- [ ] **Step 5: 提交补全引擎启用**

```bash
git add src/agent_kit/cli.py tests/test_core_cli.py
git commit -m "启用 Typer/Click 内置补全引擎"
```

---

## Chunk 2: 新增 `completion` 子命令组

### Task 3: 为 `completion` 模块写红测

**Files:**
- Create: `tests/test_completion.py`

- [ ] **Step 1: 为 oh-my-zsh 环境检测写失败测试**

```python
from pathlib import Path

def test_detect_omz_returns_custom_dir_when_env_set(monkeypatch, tmp_path):
    """当 ZSH_CUSTOM 环境变量存在时，应返回对应路径。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import detect_omz_custom_dir
    result = detect_omz_custom_dir()
    assert result == custom_dir

def test_detect_omz_returns_default_when_env_not_set_but_dir_exists(monkeypatch, tmp_path):
    """当 ZSH_CUSTOM 未设置但 ~/.oh-my-zsh/custom 存在时，应返回默认路径。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    default_dir = tmp_path / ".oh-my-zsh" / "custom"
    default_dir.mkdir(parents=True)
    from agent_kit.completion import detect_omz_custom_dir
    result = detect_omz_custom_dir(home=tmp_path)
    assert result == default_dir

def test_detect_omz_returns_none_when_no_omz(monkeypatch, tmp_path):
    """当 oh-my-zsh 环境完全不存在时，应返回 None。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import detect_omz_custom_dir
    result = detect_omz_custom_dir(home=tmp_path)
    assert result is None
```

- [ ] **Step 2: 为补全脚本生成写失败测试**

```python
def test_generate_completion_script_contains_compdef_for_agent_kit_and_ak():
    """生成的补全脚本应同时包含 agent-kit 和 ak 的 compdef 注册。"""
    from agent_kit.completion import generate_zsh_completion_script
    script = generate_zsh_completion_script()
    assert "compdef _agent-kit agent-kit" in script or "compdef _agent_kit agent-kit" in script
    assert "compdef _agent-kit ak" in script or "compdef _agent_kit ak" in script

def test_generate_completion_script_contains_complete_env_var():
    """生成的补全脚本应包含 _AGENT_KIT_COMPLETE 环境变量调用。"""
    from agent_kit.completion import generate_zsh_completion_script
    script = generate_zsh_completion_script()
    assert "_AGENT_KIT_COMPLETE" in script

def test_generate_completion_script_has_compdef_header():
    """生成的补全脚本应以 #compdef 开头。"""
    from agent_kit.completion import generate_zsh_completion_script
    script = generate_zsh_completion_script()
    assert script.startswith("#compdef ")
```

- [ ] **Step 3: 为 oh-my-zsh 安装路径写失败测试**

```python
def test_install_omz_creates_plugin_dir_and_files(monkeypatch, tmp_path):
    """oh-my-zsh 安装模式应创建 _agent-kit 和 agent-kit.plugin.zsh 两个文件。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion
    result = install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    assert (plugin_dir / "_agent-kit").exists()
    assert (plugin_dir / "agent-kit.plugin.zsh").exists()
    assert result.method == "omz"

def test_install_omz_plugin_zsh_contains_fpath_and_compdef(monkeypatch, tmp_path):
    """oh-my-zsh 插件入口应包含 fpath 注册和 compdef 声明。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion
    install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    plugin_zsh = (plugin_dir / "agent-kit.plugin.zsh").read_text(encoding="utf-8")
    assert "fpath=" in plugin_zsh
    assert "compdef" in plugin_zsh
    assert "ak" in plugin_zsh
```

- [ ] **Step 4: 为标准 Zsh（非 oh-my-zsh）安装路径写失败测试**

```python
def test_install_zfunc_creates_completion_file(monkeypatch, tmp_path):
    """当 oh-my-zsh 不存在时，应将补全脚本写入 ~/.zfunc/_agent-kit。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion
    result = install_zsh_completion(home=tmp_path)
    zfunc_file = tmp_path / ".zfunc" / "_agent-kit"
    assert zfunc_file.exists()
    assert result.method == "zfunc"

def test_install_zfunc_script_contains_complete_env_var(monkeypatch, tmp_path):
    """标准路径安装的补全脚本应包含 _AGENT_KIT_COMPLETE 环境变量。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion
    install_zsh_completion(home=tmp_path)
    content = (tmp_path / ".zfunc" / "_agent-kit").read_text(encoding="utf-8")
    assert "_AGENT_KIT_COMPLETE" in content
```

- [ ] **Step 5: 为卸载逻辑写失败测试**

```python
def test_remove_omz_deletes_plugin_dir(monkeypatch, tmp_path):
    """卸载应删除 oh-my-zsh 插件目录。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion, remove_zsh_completion
    install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    assert plugin_dir.exists()
    result = remove_zsh_completion(home=tmp_path)
    assert not plugin_dir.exists()
    assert result.removed is True

def test_remove_zfunc_deletes_completion_file(monkeypatch, tmp_path):
    """卸载应删除 ~/.zfunc/_agent-kit 文件。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion, remove_zsh_completion
    install_zsh_completion(home=tmp_path)
    zfunc_file = tmp_path / ".zfunc" / "_agent-kit"
    assert zfunc_file.exists()
    result = remove_zsh_completion(home=tmp_path)
    assert not zfunc_file.exists()
    assert result.removed is True

def test_remove_when_not_installed_returns_not_removed(monkeypatch, tmp_path):
    """当补全未安装时，卸载应返回 removed=False 而非报错。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import remove_zsh_completion
    result = remove_zsh_completion(home=tmp_path)
    assert result.removed is False
```

- [ ] **Step 6: 为重复安装的幂等性写失败测试**

```python
def test_install_is_idempotent(monkeypatch, tmp_path):
    """重复安装应覆盖已有文件而非报错。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion
    result1 = install_zsh_completion(home=tmp_path)
    result2 = install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    assert (plugin_dir / "_agent-kit").exists()
    assert (plugin_dir / "agent-kit.plugin.zsh").exists()
```

- [ ] **Step 7: 运行测试确认红灯**

Run: `uv run pytest tests/test_completion.py -v`
Expected: FAIL，因为 `agent_kit.completion` 模块尚不存在

- [ ] **Step 8: 提交测试脚手架**

```bash
git add tests/test_completion.py
git commit -m "补充 completion 子命令组红测"
```

### Task 4: 实现 `completion.py` 核心模块

**Files:**
- Create: `src/agent_kit/completion.py`

- [ ] **Step 1: 实现 oh-my-zsh 环境检测**

```python
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
```

- [ ] **Step 2: 实现补全脚本生成**

```python
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
```

- [ ] **Step 3: 实现 oh-my-zsh 插件入口生成**

```python
def generate_omz_plugin_zsh() -> str:
    """生成 oh-my-zsh 插件入口文件内容。"""
    return "\n".join([
        MANAGED_COMPLETION_MARKER + " plugin",
        "fpath=(${0:A:h} $fpath)",
        "compdef _agent-kit agent-kit",
        "compdef _agent-kit ak",
        "",
    ])
```

- [ ] **Step 4: 实现安装逻辑（oh-my-zsh + 标准 zfunc 两种路径）**

定义安装结果数据类和安装函数：

```python
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
```

- [ ] **Step 5: 实现卸载逻辑**

```python
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
```

- [ ] **Step 6: 运行测试确认转绿**

Run: `uv run pytest tests/test_completion.py -v`
Expected: PASS

- [ ] **Step 7: 提交 completion 模块**

```bash
git add src/agent_kit/completion.py
git commit -m "新增 completion 核心模块"
```

### Task 5: 为 CLI 集成写红测

**Files:**
- Modify: `tests/test_core_cli.py`

- [ ] **Step 1: 为 `completion` 子命令在 help 中可见写失败测试**

```python
def test_completion_subcommand_appears_in_help():
    """completion 子命令应出现在主帮助输出中。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "completion" in result.output
```

- [ ] **Step 2: 为 `completion install` 命令写失败测试**

```python
def test_completion_install_command_exists():
    """completion install 子命令应可调用。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["completion", "install", "--help"])
    assert result.exit_code == 0
    assert "install" in result.output.lower() or "--shell" in result.output
```

- [ ] **Step 3: 为 `completion show` 命令写失败测试**

```python
def test_completion_show_outputs_script():
    """completion show 应输出补全脚本内容。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["completion", "show"])
    assert result.exit_code == 0
    assert "_AGENT_KIT_COMPLETE" in result.output
    assert "compdef" in result.output
```

- [ ] **Step 4: 为 `completion remove` 命令写失败测试**

```python
def test_completion_remove_command_exists():
    """completion remove 子命令应可调用。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["completion", "remove", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 5: 为 `RESERVED_COMMAND_NAMES` 包含 `completion` 写失败测试**

```python
def test_reserved_command_names_includes_completion():
    """RESERVED_COMMAND_NAMES 应包含 'completion'。"""
    cli = require_module("agent_kit.cli")
    assert "completion" in cli.RESERVED_COMMAND_NAMES
```

- [ ] **Step 6: 运行测试确认红灯**

Run: `uv run pytest tests/test_core_cli.py -k "completion" -v`
Expected: FAIL

### Task 6: 在 CLI 中注册 `completion` 子命令组

**Files:**
- Modify: `src/agent_kit/cli.py`
- Modify: `src/agent_kit/messages.py`

- [ ] **Step 1: 更新 `RESERVED_COMMAND_NAMES`**

```python
RESERVED_COMMAND_NAMES = frozenset({"plugins", "config", "alias", "completion"})
```

- [ ] **Step 2: 在 `messages.py` 中添加 `completion` 相关翻译键**

英文翻译键（`"en"` 分区）：

```python
"completion.help": "Manage shell completion for agent-kit.",
"completion.install.help": "Install shell completion script.",
"completion.show.help": "Show the shell completion script.",
"completion.remove.help": "Remove installed shell completion.",
"completion.install.omz": "Installed oh-my-zsh plugin at {path}. Add 'agent-kit' to plugins=(...) in ~/.zshrc.",
"completion.install.zfunc": "Installed completion to {path}. Add 'fpath=(~/.zfunc $fpath)' and 'autoload -Uz compinit && compinit' to ~/.zshrc.",
"completion.remove.done": "Removed completion from {path}.",
"completion.remove.not_found": "No completion installation found.",
"completion.shell.unsupported": "Unsupported shell: {shell}. Currently only zsh is supported.",
```

中文翻译键（`"zh-CN"` 分区）：

```python
"completion.help": "管理 agent-kit 的 Shell 补全。",
"completion.install.help": "安装 Shell 补全脚本。",
"completion.show.help": "显示 Shell 补全脚本。",
"completion.remove.help": "卸载已安装的 Shell 补全。",
"completion.install.omz": "已安装 oh-my-zsh 插件到 {path}。请在 ~/.zshrc 的 plugins=(...) 中添加 'agent-kit'。",
"completion.install.zfunc": "已安装补全脚本到 {path}。请在 ~/.zshrc 中添加 'fpath=(~/.zfunc $fpath)' 和 'autoload -Uz compinit && compinit'。",
"completion.remove.done": "已从 {path} 卸载补全。",
"completion.remove.not_found": "未找到已安装的补全。",
"completion.shell.unsupported": "不支持的 Shell：{shell}。当前仅支持 zsh。",
```

- [ ] **Step 3: 在 `cli.py` 中创建 `completion_app` 并注册子命令**

在 `create_app()` 函数中，仿照 `alias_app` 模式新增：

```python
from agent_kit.completion import (
    generate_zsh_completion_script,
    install_zsh_completion,
    remove_zsh_completion,
)

completion_app = typer.Typer(help=_t(language, "completion.help"), no_args_is_help=True)

@completion_app.command("install", help=_t(language, "completion.install.help"))
def completion_install_command(
    shell: str = typer.Option("zsh", "--shell", "-s", help="Shell type"),
) -> None:
    if shell != "zsh":
        typer.secho(
            _t(language, "completion.shell.unsupported", shell=shell),
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=1)
    result = install_zsh_completion()
    key = f"completion.install.{result.method}"
    typer.echo(_t(language, key, path=result.path))

@completion_app.command("show", help=_t(language, "completion.show.help"))
def completion_show_command(
    shell: str = typer.Option("zsh", "--shell", "-s", help="Shell type"),
) -> None:
    if shell != "zsh":
        typer.secho(
            _t(language, "completion.shell.unsupported", shell=shell),
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(generate_zsh_completion_script())

@completion_app.command("remove", help=_t(language, "completion.remove.help"))
def completion_remove_command(
    shell: str = typer.Option("zsh", "--shell", "-s", help="Shell type"),
) -> None:
    if shell != "zsh":
        typer.secho(
            _t(language, "completion.shell.unsupported", shell=shell),
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=1)
    result = remove_zsh_completion()
    if result.removed:
        typer.echo(_t(language, "completion.remove.done", path=result.path))
    else:
        typer.echo(_t(language, "completion.remove.not_found"))

# 注册
app.add_typer(completion_app, name="completion")
```

- [ ] **Step 4: 运行测试确认转绿**

Run: `uv run pytest tests/test_core_cli.py -k "completion" -v`
Expected: PASS

- [ ] **Step 5: 提交 CLI 集成**

```bash
git add src/agent_kit/cli.py src/agent_kit/messages.py
git commit -m "注册 completion 子命令组"
```

---

## Chunk 3: 补全脚本内容与 `ak` 别名覆盖

### Task 7: 为补全脚本内容与 `ak` 覆盖写红测

**Files:**
- Modify: `tests/test_completion.py`

- [ ] **Step 1: 为补全脚本包含 managed marker 写测试**

```python
def test_completion_script_contains_managed_marker():
    """补全脚本应包含 managed marker 以便卸载时识别。"""
    from agent_kit.completion import generate_zsh_completion_script, MANAGED_COMPLETION_MARKER
    script = generate_zsh_completion_script()
    assert MANAGED_COMPLETION_MARKER in script
```

- [ ] **Step 2: 为 oh-my-zsh 插件入口内容写测试**

```python
def test_omz_plugin_zsh_contains_managed_marker():
    """oh-my-zsh 插件入口应包含 managed marker。"""
    from agent_kit.completion import generate_omz_plugin_zsh, MANAGED_COMPLETION_MARKER
    content = generate_omz_plugin_zsh()
    assert MANAGED_COMPLETION_MARKER in content

def test_omz_plugin_zsh_registers_ak_alias():
    """oh-my-zsh 插件入口应同时注册 agent-kit 和 ak 两个命令的补全。"""
    from agent_kit.completion import generate_omz_plugin_zsh
    content = generate_omz_plugin_zsh()
    assert "agent-kit" in content
    assert "ak" in content
    assert "compdef" in content
```

- [ ] **Step 3: 为安装后文件内容正确性写测试**

```python
def test_installed_omz_completion_file_matches_generated_script(monkeypatch, tmp_path):
    """安装到 oh-my-zsh 的 _agent-kit 文件内容应与生成的脚本一致。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion, generate_zsh_completion_script
    install_zsh_completion(home=tmp_path)
    installed = (custom_dir / "plugins" / "agent-kit" / "_agent-kit").read_text(encoding="utf-8")
    expected = generate_zsh_completion_script()
    assert installed == expected

def test_installed_zfunc_file_matches_generated_script(monkeypatch, tmp_path):
    """安装到 ~/.zfunc 的 _agent-kit 文件内容应与生成的脚本一致。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion, generate_zsh_completion_script
    install_zsh_completion(home=tmp_path)
    installed = (tmp_path / ".zfunc" / "_agent-kit").read_text(encoding="utf-8")
    expected = generate_zsh_completion_script()
    assert installed == expected
```

- [ ] **Step 4: 运行测试确认全绿**

Run: `uv run pytest tests/test_completion.py -v`
Expected: PASS

---

## Chunk 4: CLI 端到端测试

### Task 8: 为 `completion` CLI 命令写端到端测试

**Files:**
- Modify: `tests/test_core_cli.py`

- [ ] **Step 1: 为 `completion show` 输出正确性写测试**

```python
def test_completion_show_zsh_outputs_valid_script():
    """completion show --shell zsh 应输出包含 compdef 和 _AGENT_KIT_COMPLETE 的脚本。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["completion", "show", "--shell", "zsh"])
    assert result.exit_code == 0
    assert "compdef" in result.output
    assert "_AGENT_KIT_COMPLETE" in result.output
    assert "agent-kit" in result.output
    assert "ak" in result.output
```

- [ ] **Step 2: 为 `completion show` 不支持的 shell 写测试**

```python
def test_completion_show_unsupported_shell_fails():
    """completion show --shell bash 应报错退出（当前仅支持 zsh）。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["completion", "show", "--shell", "bash"])
    assert result.exit_code != 0
```

- [ ] **Step 3: 为 `completion install` 不支持的 shell 写测试**

```python
def test_completion_install_unsupported_shell_fails():
    """completion install --shell fish 应报错退出。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["completion", "install", "--shell", "fish"])
    assert result.exit_code != 0
```

- [ ] **Step 4: 为 `completion remove` 不支持的 shell 写测试**

```python
def test_completion_remove_unsupported_shell_fails():
    """completion remove --shell powershell 应报错退出。"""
    cli = require_module("agent_kit.cli")
    manager = SimpleNamespace(runnable_plugins=lambda: [], broken_plugins=lambda: [])
    app = cli.create_app(manager_factory=lambda: manager)
    result = CliRunner().invoke(app, ["completion", "remove", "--shell", "powershell"])
    assert result.exit_code != 0
```

- [ ] **Step 5: 运行 CLI 测试确认全绿**

Run: `uv run pytest tests/test_core_cli.py -k "completion" -v`
Expected: PASS

- [ ] **Step 6: 提交 CLI 端到端测试**

```bash
git add tests/test_core_cli.py
git commit -m "补充 completion CLI 端到端测试"
```

---

## Chunk 5: 翻译键覆盖测试

### Task 9: 为 `completion` 翻译键写测试

**Files:**
- Modify: `tests/test_completion.py`

- [ ] **Step 1: 为英文翻译键完整性写测试**

```python
def test_completion_translation_keys_exist_in_english():
    """所有 completion 相关翻译键应存在于英文 catalog 中。"""
    from agent_kit.messages import MESSAGES
    en = MESSAGES["en"]
    required_keys = [
        "completion.help",
        "completion.install.help",
        "completion.show.help",
        "completion.remove.help",
        "completion.install.omz",
        "completion.install.zfunc",
        "completion.remove.done",
        "completion.remove.not_found",
        "completion.shell.unsupported",
    ]
    for key in required_keys:
        assert key in en, f"Missing English translation key: {key}"
```

- [ ] **Step 2: 为中文翻译键完整性写测试**

```python
def test_completion_translation_keys_exist_in_chinese():
    """所有 completion 相关翻译键应存在于中文 catalog 中。"""
    from agent_kit.messages import MESSAGES
    zh = MESSAGES["zh-CN"]
    required_keys = [
        "completion.help",
        "completion.install.help",
        "completion.show.help",
        "completion.remove.help",
        "completion.install.omz",
        "completion.install.zfunc",
        "completion.remove.done",
        "completion.remove.not_found",
        "completion.shell.unsupported",
    ]
    for key in required_keys:
        assert key in zh, f"Missing Chinese translation key: {key}"
```

- [ ] **Step 3: 为翻译键中英文一一对应写测试**

```python
def test_completion_translation_keys_consistent_between_en_and_zh():
    """英文和中文的 completion 翻译键集合应一致。"""
    from agent_kit.messages import MESSAGES
    en_keys = {k for k in MESSAGES["en"] if k.startswith("completion.")}
    zh_keys = {k for k in MESSAGES["zh-CN"] if k.startswith("completion.")}
    assert en_keys == zh_keys
```

- [ ] **Step 4: 运行翻译键测试**

Run: `uv run pytest tests/test_completion.py -k "translation" -v`
Expected: PASS

---

## Chunk 6: 文档与注册更新

### Task 10: 更新文档

**Files:**
- Modify: `README.md`
- Modify: `src/agent_kit/AGENTS.md`
- Modify: `AGENTS.md`（如有必要）

- [ ] **Step 1: 在 `README.md` 中增加补全安装说明**

新增一个 `## Shell 补全` 段落，内容包括：

- `agent-kit completion install` 安装补全
- `agent-kit completion show` 查看补全脚本
- `agent-kit completion remove` 卸载补全
- 当前仅支持 Zsh
- oh-my-zsh 用户需在 `plugins=(...)` 中添加 `agent-kit`
- 非 oh-my-zsh 用户需在 `~/.zshrc` 中添加 `fpath` 配置
- 补全同时覆盖 `agent-kit` 和 `ak` 两个命令

- [ ] **Step 2: 更新 `src/agent_kit/AGENTS.md`**

在关键文件列表中新增 `completion.py` 条目，说明：
- 该模块负责 Shell 补全脚本的生成、安装和卸载
- 支持 oh-my-zsh 和标准 Zsh 两种安装路径
- 补全数据源依赖 Typer/Click 内置补全引擎

在修改 Core 时的关注点中补充 `completion` 子命令。

- [ ] **Step 3: 确认 `RESERVED_COMMAND_NAMES` 在 AGENTS 相关说明中已覆盖**

检查 `src/agent_kit/AGENTS.md` 中的命令列表是否已包含 `completion`。

- [ ] **Step 4: 提交文档更新**

```bash
git add README.md src/agent_kit/AGENTS.md
git commit -m "更新文档：补全安装说明与 AGENTS 关键文件"
```

---

## Chunk 7: 完整验证与收尾

### Task 11: 完整验证

- [ ] **Step 1: 运行 completion 模块测试**

Run: `uv run pytest tests/test_completion.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行 CLI 测试**

Run: `uv run pytest tests/test_core_cli.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 运行全量测试确认无回归**

Run: `uv run pytest`
Expected: 全部 PASS

- [ ] **Step 4: CLI smoke check**

Run:

```bash
uv run agent-kit --help
uv run agent-kit completion --help
uv run agent-kit completion show
uv run agent-kit completion show --shell zsh
```

Expected:
- `--help` 输出中包含 `completion` 子命令
- `--help` 输出中不包含 `--install-completion` 和 `--show-completion`
- `completion show` 输出包含 `compdef` 和 `ak`

- [ ] **Step 5: 检查 diff 质量**

Run: `git diff --check`
Expected: 无输出

- [ ] **Step 6: 核对工作区状态**

Run: `git status --short`
Expected: 只剩下本任务预期文件，或为空

- [ ] **Step 7: 使用 `core-release-followup` skill 完成 core 升版收尾**

因为本次改动涉及 `src/agent_kit/` 下的非插件代码，根据仓库规则，功能提交完成后必须补做一次 core 版本升级流程。

---

## 测试覆盖矩阵

| 测试目标 | 测试文件 | 测试函数前缀 |
|---------|---------|------------|
| 补全引擎启用（无 `add_completion=False`） | `tests/test_core_cli.py` | `test_app_has_completion_enabled` |
| Typer 默认补全选项隐藏 | `tests/test_core_cli.py` | `test_typer_default_completion_options_are_hidden` |
| oh-my-zsh 环境检测 | `tests/test_completion.py` | `test_detect_omz_*` |
| 补全脚本生成（内容正确性） | `tests/test_completion.py` | `test_generate_completion_script_*` |
| oh-my-zsh 安装路径 | `tests/test_completion.py` | `test_install_omz_*` |
| 标准 Zsh 安装路径 | `tests/test_completion.py` | `test_install_zfunc_*` |
| 卸载逻辑 | `tests/test_completion.py` | `test_remove_*` |
| 安装幂等性 | `tests/test_completion.py` | `test_install_is_idempotent` |
| 安装后文件内容一致性 | `tests/test_completion.py` | `test_installed_*_matches_generated_script` |
| Managed marker 存在性 | `tests/test_completion.py` | `test_*_contains_managed_marker` |
| `ak` 别名补全注册 | `tests/test_completion.py` | `test_omz_plugin_zsh_registers_ak_alias` |
| CLI `completion` 子命令可见 | `tests/test_core_cli.py` | `test_completion_subcommand_appears_in_help` |
| CLI `completion install` 可调用 | `tests/test_core_cli.py` | `test_completion_install_command_exists` |
| CLI `completion show` 输出正确 | `tests/test_core_cli.py` | `test_completion_show_*` |
| CLI `completion remove` 可调用 | `tests/test_core_cli.py` | `test_completion_remove_command_exists` |
| 不支持的 Shell 报错 | `tests/test_core_cli.py` | `test_completion_*_unsupported_shell_fails` |
| `RESERVED_COMMAND_NAMES` 包含 completion | `tests/test_core_cli.py` | `test_reserved_command_names_includes_completion` |
| 英文翻译键完整性 | `tests/test_completion.py` | `test_completion_translation_keys_exist_in_english` |
| 中文翻译键完整性 | `tests/test_completion.py` | `test_completion_translation_keys_exist_in_chinese` |
| 中英文键一致性 | `tests/test_completion.py` | `test_completion_translation_keys_consistent_*` |

## 文件影响范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/agent_kit/cli.py` | 修改 | 移除 `add_completion=False`，隐藏 Typer 默认补全选项，注册 `completion` 子命令组 |
| `src/agent_kit/completion.py` | 新增 | 补全管理核心逻辑（检测、生成、安装、卸载） |
| `src/agent_kit/messages.py` | 修改 | 新增 `completion.*` 翻译键（中英文） |
| `tests/test_completion.py` | 新增 | 补全模块单元测试 |
| `tests/test_core_cli.py` | 修改 | 补全 CLI 端到端测试 |
| `README.md` | 修改 | 补全安装说明 |
| `src/agent_kit/AGENTS.md` | 修改 | 记录 `completion.py` 模块 |

## 实施备注

- 本计划首期只实现 Zsh 补全支持，不支持的 Shell（Bash/Fish/PowerShell）通过 `--shell` 参数提示用户并拒绝
- 后续可扩展 Bash 和 Fish 支持，只需在 `completion.py` 中增加对应的脚本生成和安装逻辑
- 补全底层完全依赖 Typer/Click 的内置补全机制，每次 Tab 按键都会触发 Python 进程，可能有 0.2–0.5 秒延迟
- oh-my-zsh 检测优先使用 `$ZSH_CUSTOM` 环境变量，其次回退到 `~/.oh-my-zsh/custom` 默认路径
- 安装操作是幂等的，重复安装会覆盖已有文件
- 卸载操作在未找到安装时不报错，只返回 `removed=False`
- 补全脚本中使用 `COMP_WORDS` 和 `COMP_CWORD` 是 Typer/Click 的 `zsh_complete` 模式所需的 bash 风格桥接变量，Click 内部会将 Zsh 原生的 `words`/`CURRENT` 映射到这些变量上完成补全计算，这是 Click 的标准行为
- oh-my-zsh 插件入口中 `fpath=(${0:A:h} $fpath)` 采用前置方式，确保 agent-kit 的补全定义优先于其他可能冲突的补全
