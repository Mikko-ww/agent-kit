# opencode-env-switch Profile 自动创建功能设计

## 摘要

为 `opencode-env-switch` 插件的 `profile add` 和 `wizard` 命令新增"自动创建"模式。用户可在插件配置目录下自动生成 profile 目录结构与带注释模板文件，同时保留原有的手动输入路径方式。

## 背景

当前 `profile add` 和 `wizard` 要求用户提供已存在的配置文件路径或目录路径。路径校验会检查文件/目录必须已存在且类型正确。这意味着用户必须先在外部手动创建好配置文件，再回来把路径填入 profile。

对于新用户或需要统一管理多个 profile 的场景，这增加了操作负担。本设计新增自动创建模式，在插件的受管目录下按 profile 名自动生成标准目录结构和模板配置文件。

## 自动创建的目录结构

```
~/.config/agent-kit/plugins/opencode-env-switch/
├── config.jsonc          (已有的插件主配置)
├── zsh/active.zsh        (已有的受管 zsh 文件)
└── profiles/
    └── <profile-name>/
        ├── opencode.jsonc    (带注释的 OpenCode 配置模板)
        └── tui.json          (最小 TUI 配置模板)
```

若用户在自动创建流程中为 `config_dir` 选择自动创建，则 `OPENCODE_CONFIG_DIR` 指向 `profiles/<profile-name>/` 根目录本身，不再创建 `config/` 子目录。

## 涉及文件

- `packages/opencode-env-switch/src/opencode_env_switch/logic.py` — 新增 `create_profile_directory()` 和 `AutoCreateResult`
- `packages/opencode-env-switch/src/opencode_env_switch/config.py` — 新增 `profiles_base_path()`
- `packages/opencode-env-switch/src/opencode_env_switch/plugin_cli.py` — 修改 `profile_add_command`、`wizard_command`
- `packages/opencode-env-switch/src/opencode_env_switch/messages.py` — 新增中英文消息键
- `packages/opencode-env-switch/tests/test_env_switch_cli.py` — 新增 CLI 测试
- `packages/opencode-env-switch/tests/test_env_switch_logic.py` — 新增 logic 测试

## 详细设计

### 1. config.py 新增

新增 `profiles_base_path()` 辅助函数，返回 profiles 目录的基础路径：

```python
def profiles_base_path(config_root: Path) -> Path:
    return config_root / "plugins" / PLUGIN_ID / "profiles"
```

### 2. logic.py 新增

新增数据类 `AutoCreateResult` 和函数 `create_profile_directory()`：

```python
OPENCODE_CONFIG_TEMPLATE = """\
// OpenCode configuration file
// See https://opencode.ai for documentation
{
  // Add your OpenCode configuration here
}
"""

TUI_CONFIG_TEMPLATE = "{}\n"

@dataclass(slots=True, frozen=True)
class AutoCreateResult:
    opencode_config: Path | None
    tui_config: Path | None
    config_dir: Path | None

def create_profile_directory(
    config_root: Path,
    profile_name: str,
    *,
    create_opencode_config: bool = False,
    create_tui_config: bool = False,
    create_config_dir: bool = False,
) -> AutoCreateResult:
```

行为：
- 计算 profile 目录路径为 `profiles_base_path(config_root) / profile_name`
- 如果该目录已存在，抛 `ValueError`
- 创建 profile 目录
- 按参数创建对应的模板文件/子目录
- 返回已创建路径的 `AutoCreateResult`（未创建的项为 `None`）

### 3. profile add 命令变更

新增 `--auto-create` flag：

**非交互模式**（带 `--auto-create`）：
- 三个路径 flag 全空 → 全部自动创建
- 某个路径已手动指定 → 该路径不自动创建，其余自动创建

**交互模式**（无路径参数且无 `--auto-create`）：
- 对每个路径显示三选一选项：自动创建（推荐） / 输入已有路径 / 跳过
- 选"自动创建" → 记录该项需要自动创建
- 选"输入已有路径" → 走现有 `_prompt_optional_file_path` / `_prompt_optional_dir_path`
- 选"跳过" → 设为 `None`

### 4. Wizard 变更

在输入 profile name/description 后、配置路径前，新增模式选择步骤：

- 选自动创建（推荐）：显示将要创建的目录路径，逐项 confirm（默认 yes）
- 选手动输入：走现有流程

### 5. 错误处理

- 目录已存在：`ValueError("profile directory already exists: {path}")`
- 磁盘权限/空间问题：标准 `OSError` 上浮到 CLI 层处理
- 回滚策略：若 `create_profile_directory` 成功但后续 `add_profile` 失败（如 profile 重名），需 `shutil.rmtree` 清理已创建的目录

### 6. 消息新增

在 `messages.py` 的 `en` 和 `zh-CN` 中各新增消息键，涵盖：
- `option.auto_create` — CLI help
- `prompt.path_mode` / `prompt.path_mode.auto` / `prompt.path_mode.manual` — 模式选择
- `prompt.auto_create_*` — 逐项确认
- `prompt.path_action.*` — 三选一选项
- `result.auto_created_*` — 创建结果
- `error.profile_dir_exists` — 错误提示
- `wizard.step_path_mode` / `wizard.auto_create_base_path` — wizard 步骤

### 7. 测试计划

- `create_profile_directory` 单元测试
- `profile add --auto-create` 非交互全自动
- `profile add --auto-create --tui-config /path` 混合模式
- `profile add` 交互模式三选一
- Wizard 自动创建模式
- Wizard 手动模式不受影响
- 中英文消息覆盖
- 回滚清理验证

### 8. 文档更新

- `README.md`：新增 `--auto-create` 用法，更新 wizard 描述
- `AGENTS.md`：更新业务规则
