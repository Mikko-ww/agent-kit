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
agent-kit opencode-env-switch profile update --name work --description "new description"
agent-kit opencode-env-switch profile remove --name work
agent-kit opencode-env-switch switch --name work
agent-kit opencode-env-switch export --name work --shell zsh
agent-kit opencode-env-switch status
```

## 行为约束

- v1 只支持 zsh，不处理 bash/fish
- profile 只引用外部路径，不复制配置资产
- 每个 profile 至少要声明 `opencode_config`、`tui_config`、`config_dir` 中的一项
- `switch` 和 `export` 会校验 profile 中所有已声明路径
- 切换时对未声明的受管变量显式 `unset`，避免旧 profile 残留
- `init zsh` 只在 `.zshrc` 中维护一个带 marker 的 `source` 块，重复执行必须幂等
- `profile remove` 默认不允许删除当前 active profile
