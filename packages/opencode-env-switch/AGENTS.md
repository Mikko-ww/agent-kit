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
- `agent-kit opencode-env-switch wizard`

core 侧当前还提供固定短名 alias：

- `agent-kit oes ...` 等价于 `agent-kit opencode-env-switch ...`

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
- `active_profile`（可为已注册的 profile 名，或虚拟目标 `default`）
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
- profile 可保存外部路径引用，也可通过 `--auto-create` 在受管目录下自动创建配置文件
- 自动创建的 profile 文件统一位于 `{config_root}/plugins/opencode-env-switch/profiles/<name>/`
- 自动创建时可生成 `opencode.jsonc`（带注释模板）、`tui.json`（最小模板）；若用户选择为 `config_dir` 自动创建，则 `OPENCODE_CONFIG_DIR` 指向 `profiles/<name>/` 根目录，不再额外创建 `profiles/<name>/config/` 子目录
- 若 `profiles/<name>/` 目录已存在则拒绝自动创建
- `profile add --auto-create` 支持与手动路径参数混合使用
- 交互模式下对每个路径提供"自动创建 / 输入已有路径 / 跳过"三选一
- wizard 是通用配置管理入口，不再限定为首次引导
- wizard 直接通过 `agent-kit opencode-env-switch wizard` 进入交互，不再使用 `wizard default`
- wizard 主菜单至少覆盖：新增 profile、更新已有 profile、切换 active profile、初始化/修复 zsh 集成、查看状态
- wizard 在新增或更新路径时，需要支持自动创建与手动输入两种模式
- 每个 profile 至少声明一个受管路径
- 虚拟切换目标 `default`（保留名，不可作为用户自定义 profile 名称）：`switch` / `export` 选择后受管 `active.zsh` 对 `OPENCODE_CONFIG`、`OPENCODE_TUI_CONFIG`、`OPENCODE_CONFIG_DIR` 全部 `unset`，由 shell 恢复未受插件覆盖的行为；交互式切换列表中 `default` 固定为第一项
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
- `profile add --auto-create` 是否正确在受管目录下创建模板文件
- `profile add --auto-create` 与手动路径混合时是否只自动创建未指定的路径
- 自动创建失败（如 profile 重名）时是否回滚已创建的目录
- wizard 是否在已有配置基础上操作，而不是覆盖旧 profile
- wizard 的自动创建模式是否正确生成文件并记录路径
- wizard 更新已有 profile 时是否复用受管目录而不破坏已有文件
- `switch` 是否正确更新 `active_profile` 并输出完整 `export`/`unset`
- `export` 是否输出可直接用于 zsh 的 shell 片段
- `status` 是否正确反映 zsh 接入状态、受管文件状态和 profile 路径有效性
- 中英文下的 `--help`、profile 提示、warning/error、状态输出是否保持一致

相关测试：

- [tests/test_env_switch_cli.py](tests/test_env_switch_cli.py)
- [tests/test_env_switch_logic.py](tests/test_env_switch_logic.py)
