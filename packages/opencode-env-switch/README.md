# opencode-env-switch

`opencode-env-switch` 是 `agent-kit` 的第一方插件，用于通过 shell 环境变量切换 OpenCode profile，而不是直接改写 `~/.config/opencode/` 的真实配置文件。

## 核心能力

- 管理 `OPENCODE_CONFIG`
- 管理 `OPENCODE_TUI_CONFIG`
- 管理 `OPENCODE_CONFIG_DIR`
- 通过受管 `active.zsh` 提供持久化 zsh 接入
- 提供临时 `export` 输出，便于 `eval` 使用
- 提供轻交互 CLI，缺少参数时可通过选择/输入补全

## 配置文件

插件配置保存在：

```text
~/.config/agent-kit/plugins/opencode-env-switch/config.jsonc
```

配置结构：

```json
{
  "plugin_id": "opencode-env-switch",
  "config_version": 1,
  "active_profile": "work",
  "shells": {
    "zsh": {
      "rc_file": "~/.zshrc",
      "source_file": "~/.config/agent-kit/plugins/opencode-env-switch/zsh/active.zsh",
      "installed": true
    }
  },
  "profiles": [
    {
      "name": "work",
      "description": "work profile",
      "opencode_config": "/path/to/opencode-work.jsonc",
      "tui_config": "/path/to/tui-work.json",
      "config_dir": "/path/to/opencode-work-dir"
    }
  ]
}
```

## 命令

```bash
agent-kit opencode-env-switch init zsh
agent-kit opencode-env-switch profile list
agent-kit opencode-env-switch profile add --name work --opencode-config /path/to/opencode.jsonc
agent-kit opencode-env-switch profile add --name work --auto-create
agent-kit opencode-env-switch profile add --name work --auto-create --tui-config /path/to/tui.json
agent-kit opencode-env-switch profile update --name work --description "new description"
agent-kit opencode-env-switch profile remove --name work
agent-kit opencode-env-switch switch --name work
agent-kit opencode-env-switch switch --name default
agent-kit opencode-env-switch export --name work --shell zsh
agent-kit opencode-env-switch status
agent-kit opencode-env-switch wizard
```

### profile add --auto-create

`--auto-create` 选项会在插件受管目录下自动创建 profile 配置文件和目录：

```text
~/.config/agent-kit/plugins/opencode-env-switch/profiles/<name>/
├── opencode.jsonc    (带注释的配置模板，可选)
├── tui.json          (最小配置模板，可选)
```

自动创建且为 `config_dir` 选择「自动创建」时，`config_dir` 会指向上述 **profile 根目录** `profiles/<name>/`（即 `OPENCODE_CONFIG_DIR` 与该目录一致），不再生成额外的 `config/` 子目录。手动指定 `--config-dir` 或交互输入的路径不受影响。

- 单独使用 `--auto-create` 时，三个路径全部自动创建
- 可与 `--opencode-config`、`--tui-config`、`--config-dir` 组合：已手动指定的路径不自动创建，其余自动创建
- 不带 `--auto-create` 且不带路径参数时，进入交互模式，对每个路径可选择"自动创建"、"输入已有路径"或"跳过"

### wizard 命令

`wizard` 命令现在是交互式配置入口，而不是仅用于第一次初始化。直接执行：

```bash
agent-kit opencode-env-switch wizard
```

进入后会先显示管理菜单，可用于：

1. 新增 profile
2. 更新已有 profile
3. 切换当前 active profile
4. 初始化或修复 zsh 集成
5. 查看当前状态后退出

其中新增 profile 时，仍支持两种路径来源：

- 自动创建（推荐）：在 `profiles/<name>/` 下创建受管文件
- 手动输入：引用已有路径

更新已有 profile 时会在当前配置基础上操作，不会再从空默认配置起步，也不会清空已有 profile。

## CLI 语言

`opencode-env-switch` 的帮助文案、交互提示、warning/error 和状态输出都会遵从 `agent-kit` 的全局语言策略。

- 默认语言是英文
- 支持 `en` 与 `zh-CN`
- 通过 `agent-kit opencode-env-switch ...` 运行时，语言由 core 决议后透传
- 直接运行插件入口时，也会按 `AGENT_KIT_LANG`、全局 `language` 配置、系统语言、英文默认值的顺序回退

## 行为约束

- v1 只支持 zsh，不处理 bash/fish
- profile 可引用外部路径，也可通过 `--auto-create` 在受管目录下自动创建
- 自动创建的 profile 文件统一位于 `~/.config/agent-kit/plugins/opencode-env-switch/profiles/<name>/`
- 每个 profile 至少要声明 `opencode_config`、`tui_config`、`config_dir` 中的一项
- `switch` 和 `export` 会校验 profile 中所有已声明路径
- 虚拟目标 **`default`**（不可用作自定义 profile 名）：写入受管 `active.zsh` 时对上述三个变量全部 `unset`，相当于不再通过本插件覆盖 OpenCode 相关环境变量；无已注册 profile 时仍可使用 `switch` / `export` 的 `default`
- 切换时对未声明的受管变量显式 `unset`，避免旧 profile 残留
- `init zsh` 只在 `.zshrc` 中维护一个带 marker 的 `source` 块，重复执行必须幂等
- `profile remove` 默认不允许删除当前 active profile
