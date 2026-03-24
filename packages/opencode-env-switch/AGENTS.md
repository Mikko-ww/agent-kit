# opencode-env-switch 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `opencode-env-switch` 自身的业务约束。

## 1. 插件目标

`opencode-env-switch` 负责通过 shell 环境变量切换 OpenCode profile，当前不直接改写 `~/.config/opencode/` 的真实配置内容。

## 2. 命令

当前插件对外提供以下命令：

- `agent-kit opencode-env-switch init zsh`
- `agent-kit opencode-env-switch profile list`
- `agent-kit opencode-env-switch profile add`
- `agent-kit opencode-env-switch profile update`
- `agent-kit opencode-env-switch profile remove`
- `agent-kit opencode-env-switch switch`
- `agent-kit opencode-env-switch export`
- `agent-kit opencode-env-switch status`

对应实现入口：

- [src/opencode_env_switch/plugin_cli.py](src/opencode_env_switch/plugin_cli.py)
- [src/opencode_env_switch/messages.py](src/opencode_env_switch/messages.py)
- [src/opencode_env_switch/locale.py](src/opencode_env_switch/locale.py)

## 3. 配置

配置文件位置：

- `~/.config/agent-kit/plugins/opencode-env-switch/config.jsonc`

当前配置核心字段：

- `plugin_id`
- `config_version`
- `active_profile`
- `shells.zsh.rc_file`
- `shells.zsh.source_file`
- `shells.zsh.installed`
- `profiles`

其中 `profiles` 元素至少包含：

- `name`
- `description`（可选）
- `opencode_config`（可选）
- `tui_config`（可选）
- `config_dir`（可选）

配置读写实现：

- [src/opencode_env_switch/config.py](src/opencode_env_switch/config.py)

## 4. 业务规则

- v1 只支持 zsh，不处理 bash/fish
- profile 只保存外部路径引用，不复制配置资产
- 每个 profile 至少声明一个受管路径
- 受管环境变量仅包括：
  - `OPENCODE_CONFIG`
  - `OPENCODE_TUI_CONFIG`
  - `OPENCODE_CONFIG_DIR`
- `switch` 仅在目标 profile 的所有已声明路径都校验通过后，才会改写受管 `active.zsh`
- 受管 `active.zsh` 必须对未声明变量显式 `unset`
- `init zsh` 只通过 marker block 接入 `.zshrc`，重复执行必须幂等
- 不允许直接删除当前 active profile

核心业务实现：

- [src/opencode_env_switch/logic.py](src/opencode_env_switch/logic.py)

## 5. 修改本插件时重点验证

- `init zsh` 是否正确创建/更新受管 `active.zsh` 与 `.zshrc` marker block
- `profile add/update/remove/list` 是否正确维护 profile 注册表
- `switch` 是否正确更新 `active_profile` 并输出完整 `export`/`unset`
- `export` 是否输出可直接用于 zsh 的 shell 片段
- `status` 是否正确反映 zsh 接入状态、受管文件状态和 profile 路径有效性
- 中英文下的 `--help`、profile 提示、warning/error、状态输出是否保持一致

相关测试：

- [tests/test_env_switch_cli.py](tests/test_env_switch_cli.py)
- [tests/test_env_switch_logic.py](tests/test_env_switch_logic.py)
