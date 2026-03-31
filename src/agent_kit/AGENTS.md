# Core 目录说明

本目录继承根目录 [AGENTS.md](../../AGENTS.md) 的全局规则，本文只补充 core 相关约束。

## 1. 关键提醒

- 不要回退到 “core 直接在当前进程内加载插件业务实现” 的 in-process 插件模型。
- 修改官方注册表时，必须同步更新：
  - [../../registry/official.json](../../registry/official.json)
  - [official_registry.json](official_registry.json)
- 任何会影响插件安装、运行或校验逻辑的改动，都要同步检查 CLI 输出、`plugin.json` 结构和测试。
- core 负责解析 CLI 最终语言、维护全局 `config.jsonc.language`，并在启动插件进程时透传最终语言。
- core 负责管理 `agent-kit alias ...` 受管 alias wrapper 的创建、删除和状态输出。
- core 负责维护官方插件命令短名 alias，并把 alias 路由到对应 `plugin_id`。

## 2. Core 职责边界

core 负责：

- 提供根命令 `agent-kit`（含 `--version` / `-V` 输出 core 版本）
- 暴露 `agent-kit plugins <action>` 管理命令
- 暴露 `agent-kit alias <action>` alias 管理命令
- 暴露 `agent-kit completion <action>` Shell 补全管理命令
- 暴露 `agent-kit <plugin-alias> ...` 到官方插件的短名转发
- 读取并合并内置注册表与本地缓存注册表
- 安装、更新、卸载官方插件
- 支持 `pypi | git | wheel` 三种官方插件来源
- 校验插件元数据、分发包元数据、`api_version` 与 `config_version`
- 将 `agent-kit <plugin-id> ...` 转发到插件独立环境里的 `agent-kit-plugin`

core 不负责：

- 在当前进程内直接执行插件业务逻辑
- 保存某个插件自己的业务配置语义
- 绕过官方注册表安装任意第三方包

## 3. 关键文件

- [cli.py](cli.py)：根 CLI、`plugins` 命令空间、插件命令转发
- [completion.py](completion.py)：Shell 补全脚本的生成、安装和卸载，支持 oh-my-zsh 和标准 Zsh 两种安装路径，补全数据源依赖 Typer/Click 内置补全引擎
- [plugin_manager.py](plugin_manager.py)：插件生命周期管理与运行时校验
- [registry.py](registry.py)：注册表读取、刷新与合并
- [official_registry.json](official_registry.json)：包内置官方注册表副本
- [paths.py](paths.py)：配置、数据、缓存目录布局
- [jsonc.py](jsonc.py)：JSONC 解析与写入
- [context.py](context.py)：基础交互上下文
- [locale.py](locale.py)：全局语言决议与 `language` 配置读写
- [messages.py](messages.py)：core CLI 多语言文案
- [alias.py](alias.py)：受管 alias wrapper 的状态判断与文件操作
- [release_core.py](release_core.py)：core 版本升级、提交与 tag 编排

## 4. 目录与状态模型

当前目录布局约定：

- 配置目录：`~/.config/agent-kit`
- 数据目录：`~/.local/share/agent-kit`
- 缓存目录：`~/.cache/agent-kit`

插件相关路径约定：

- 插件配置：`~/.config/agent-kit/plugins/<plugin-id>/config.jsonc`
- 插件安装态：`~/.local/share/agent-kit/plugins/<plugin-id>/plugin.json`
- 插件虚拟环境：`~/.local/share/agent-kit/plugins/<plugin-id>/venv`
- 注册表缓存：`~/.cache/agent-kit/registry.json`
- wheel 制品缓存：`~/.cache/agent-kit/artifacts/<plugin-id>/`

## 5. 修改 Core 时的关注点

- 改 CLI 时，确认 `agent-kit --help`、`agent-kit plugins ...`、`agent-kit completion ...` 和动态插件命令行为一致。
- 改 alias 行为时，确认 `agent-kit alias enable|disable|status`、`agent-kit --help`、PATH 提示和非受管文件保护行为一致。
- 改插件 alias 行为时，确认 canonical 命令、alias 命令、root help 中的 alias 提示，以及冲突保护都一致。
- 改语言或帮助输出时，确认 `agent-kit config get/set language`、`agent-kit --help`、`agent-kit plugins --help` 和插件透传语言行为一致。
- 改注册表时，确认本地内置注册表和仓库副本同步。
- 改安装逻辑时，确认安装后会校验：
  - `plugin_id`
  - `installed_version`
  - `api_version`
  - 分发包版本与来源
- 改 core 发布脚本时，确认只更新根 `pyproject.toml` 和 `src/agent_kit/__init__.py`，不会误改任何插件目录或 registry。
- 改 `wheel` 安装逻辑时，确认会先下载到缓存目录，再校验 `sha256`，最后才执行安装。
- 改运行逻辑时，确认 `config_version` 不兼容会阻止执行。

## 6. 相关测试

- [../../tests/test_core_cli.py](../../tests/test_core_cli.py)
- [../../tests/test_completion.py](../../tests/test_completion.py)
- [../../tests/test_plugin_manager.py](../../tests/test_plugin_manager.py)
- [../../tests/test_release_core.py](../../tests/test_release_core.py)

改 core 行为时，优先先补相关测试，再改实现。
