# agent-kit

`agent-kit` 是一个可扩展的 Python CLI 平台，统一入口是 `agent-kit`。

## 项目概览

- Core 负责官方插件注册表、插件安装/更新/卸载、版本校验和命令转发。
- 插件运行在各自独立环境中，core 通过子进程调用统一入口 `agent-kit-plugin`。
- 当前第一方插件包括：
  - [packages/skills-link](packages/skills-link)：把本地 skills 目录按目录粒度链接到目标目录
  - [packages/opencode-env-switch](packages/opencode-env-switch)：通过 shell 环境变量切换 OpenCode profile
  - [packages/self-evolve](packages/self-evolve)：把项目内 session 检测成 candidate/rule，并同步为统一 Skill 输出

## 插件安装模型

用户安装官方插件的入口固定是：

```bash
agent-kit plugins install <plugin-id>
```

当前 core 支持三种官方来源：

- `pypi`：从包索引安装指定分发包版本。
- `git`：从 Git 仓库的固定 `tag` 安装，可带 `subdirectory`；旧条目仍兼容 `commit`。
- `wheel`：从远程 `.whl` 制品安装。

`wheel` 来源的规则：

- 只支持远程 `.whl`，不支持本地路径，也不支持源码包。
- 安装前会先把制品下载到缓存目录。
- 下载完成后必须先做 `sha256` 校验。
- 校验通过后，才会从本地缓存的 wheel 安装到插件独立环境。
- 安装完成后仍会继续校验 `plugin_id`、`installed_version`、`api_version`、分发包名和分发包版本。

当前仓库已经具备 `wheel` 安装能力，但官方内置插件条目暂未切换到 `wheel`。目前内置的 `skills-link` 仍然使用 `git` 来源。

`git` 来源的官方发布约定：

- 官方 registry 优先使用插件级 tag 作为安装锚点，例如 `skills-link-v0.1.0`
- `commit` 不再是官方发布的必填字段；旧 registry 条目仍可兼容
- 安装后仍会校验分发包版本、仓库 URL 和插件元数据，但不再强校验 registry 中的 `commit`

## 目录布局

- 配置目录：`~/.config/agent-kit`
- 数据目录：`~/.local/share/agent-kit`
- 缓存目录：`~/.cache/agent-kit`

插件相关路径：

- 插件配置：`~/.config/agent-kit/plugins/<plugin-id>/config.jsonc`
- 插件安装态：`~/.local/share/agent-kit/plugins/<plugin-id>/plugin.json`
- 插件虚拟环境：`~/.local/share/agent-kit/plugins/<plugin-id>/venv`
- 注册表缓存：`~/.cache/agent-kit/registry.json`
- wheel 制品缓存：`~/.cache/agent-kit/artifacts/<plugin-id>/`

## 常用命令

```bash
agent-kit --version
agent-kit plugins list
agent-kit plugins info skills-link
agent-kit plugins install skills-link
agent-kit alias enable
agent-kit alias status
agent-kit alias disable
agent-kit config list
agent-kit config get language
agent-kit config set language zh-CN
agent-kit skills-link status
agent-kit sl status
agent-kit plugins info opencode-env-switch
agent-kit opencode-env-switch status
agent-kit oes status
agent-kit plugins info self-evolve
agent-kit self-evolve status
```

## CLI alias

core 现在支持通过受管 wrapper 显式启用 `agent-kit` 的固定别名 `ak`：

```bash
agent-kit alias enable
agent-kit alias status
agent-kit alias disable
```

行为约定：

- `agent-kit alias enable` 会创建 `~/.local/bin/ak`
- `agent-kit alias disable` 只会删除 agent-kit 自己创建的受管 wrapper，不会删除用户自定义脚本
- `agent-kit alias status` 会显示当前状态、wrapper 路径，以及 `~/.local/bin` 是否已在 `PATH`
- `ak ...` 的运行效果等价于 `agent-kit ...`

当前只支持固定别名 `ak`，不支持自定义别名名或自定义安装路径。

如果 `agent-kit alias status` 提示 `~/.local/bin` 未在 `PATH` 中，需要先把它加入 shell 的 `PATH`，否则直接输入 `ak` 不会生效。

## Plugin alias

core 还支持为官方插件提供固定短名：

- `skills-link -> sl`
- `opencode-env-switch -> oes`

例如：

```bash
agent-kit skills-link --help
agent-kit sl status
agent-kit sl --help
agent-kit oes status
ak sl status
ak oes status
```

行为约定：

- 插件短名由 core 内置维护，当前不支持用户自定义
- `agent-kit sl ...` 等价于 `agent-kit skills-link ...`
- `agent-kit oes ...` 等价于 `agent-kit opencode-env-switch ...`
- `agent-kit <plugin-id> --help` 和对应短名 `--help` 都会直接显示插件自己的帮助信息
- root help 会在 canonical 插件命令旁标注 alias，但 alias 本身不作为独立 help 项显示

## Shell 补全

`agent-kit` 支持 Zsh 命令补全，补全同时覆盖 `agent-kit` 和 `ak` 两个命令。

```bash
agent-kit completion install    # 安装补全
agent-kit completion show       # 查看补全脚本
agent-kit completion remove     # 卸载补全
```

当前仅支持 Zsh。安装时会自动检测 oh-my-zsh 环境：

- **oh-my-zsh 用户**：补全脚本安装到 `$ZSH_CUSTOM/plugins/agent-kit/`，需要在 `~/.zshrc` 的 `plugins=(...)` 中添加 `agent-kit`
- **非 oh-my-zsh 用户**：补全脚本安装到 `~/.zfunc/_agent-kit`，需要在 `~/.zshrc` 中添加 `fpath=(~/.zfunc $fpath)` 和 `autoload -Uz compinit && compinit`

### 故障排查

如果补全不生效，请依次检查：

1. **验证安装位置**
   ```bash
   agent-kit completion show  # 查看补全脚本内容
   ls -la ~/.zfunc/_agent-kit  # 或检查 oh-my-zsh 插件目录
   ```

2. **oh-my-zsh 用户**：确认 `~/.zshrc` 中 `plugins=()` 包含 `agent-kit`
   ```bash
   grep "plugins=" ~/.zshrc
   # 应包含: plugins=(... agent-kit ...)
   ```

3. **非 oh-my-zsh 用户**：确认 `~/.zshrc` 包含以下配置
   ```bash
   grep -E "(fpath|compinit)" ~/.zshrc
   # 应包含:
   # fpath=(~/.zfunc $fpath)
   # autoload -Uz compinit && compinit
   ```

4. **重新加载 shell**
   ```bash
   exec zsh  # 或 source ~/.zshrc
   ```

5. **调试补全执行**（验证 agent-kit 命令可正常执行）
   ```bash
   _AGENT_KIT_COMPLETE=zsh_complete agent-kit
   # 应输出 Zsh 补全建议，而非报错
   ```


## CLI 多语言

`agent-kit` 与第一方插件当前支持 `en` 和 `zh-CN`，默认语言是英文。

语言决议顺序固定为：

1. `AGENT_KIT_LANG`
2. `~/.config/agent-kit/config.jsonc` 中的 `language`
3. 系统语言环境变量 `LC_ALL` / `LC_MESSAGES` / `LANG`
4. 英文默认值 `en`

可用命令：

```bash
agent-kit config list
agent-kit config get language
agent-kit config set language auto
agent-kit config set language en
agent-kit config set language zh-CN
```

当前支持的全局配置项：

- `language`：可选值为 `auto`、`en`、`zh-CN`

当执行 `agent-kit config set language auto` 时，core 会删除 `config.jsonc` 里的 `language` 字段，但会保留全局配置文件本身；如果文件中没有其他配置项，则会保留一个空的 JSONC 模板，方便后续继续编辑。

单次运行也可以直接覆盖：

```bash
AGENT_KIT_LANG=zh-CN agent-kit --help
AGENT_KIT_LANG=en agent-kit skills-link --help
```

如果系统语言不是当前支持的语言，CLI 会自动回退到英文。插件通过 `agent-kit <plugin-id> ...` 启动时，会自动遵从 core 透传的最终语言。

## 本地开发环境

如果你想在仓库根目录下用隔离目录做本地手工测试，可以先载入开发环境脚本：

```bash
source scripts/dev/dev-env.sh
```

脚本会在当前终端中设置以下环境变量，并自动创建对应目录：

```bash
AGENT_KIT_CONFIG_DIR="$PWD/.tmp/config"
AGENT_KIT_DATA_DIR="$PWD/.tmp/data"
AGENT_KIT_CACHE_DIR="$PWD/.tmp/cache"
```

载入后，就可以直接执行本地命令，例如：

```bash
ak plugins list
ak skills-link status
ak opencode-env-switch status
```

其中 `ak` 是 `source scripts/dev/dev-env.sh` 后注入到当前终端的 shell 函数，不等同于 `agent-kit alias enable` 创建的 `~/.local/bin/ak` wrapper。

- `ak plugins ...` 仍然等价于 `uv run agent-kit plugins ...`
- `ak skills-link ...` 会直接调用当前 workspace 中的 `skills-link` 插件
- `ak opencode-env-switch ...` 会直接调用当前 workspace 中的 `opencode-env-switch` 插件

```bash
uv run agent-kit plugins list
```

## 插件发布脚本

仓库内新增单插件发布脚本：

```bash
./scripts/release/ak-release.sh skills-link patch
./scripts/release/ak-release.sh skills-link minor
./scripts/release/ak-release.sh skills-link major
```

底层实现仍然保留为：

```bash
uv run python scripts/release/release_plugin.py <plugin-id> patch
uv run python scripts/release/release_plugin.py <plugin-id> minor
uv run python scripts/release/release_plugin.py <plugin-id> major
```

第一版行为固定为：

- 优先推荐使用 `./scripts/release/ak-release.sh`
- 只处理单个官方插件
- 参数缺失或错误时，会直接输出用法、可用插件和可用版本类型提示
- 自动更新插件版本号
- 自动执行 `uv lock`，并在有变化时把 `uv.lock` 纳入同一次发布提交
- 自动同步两个官方 registry 副本中的 `version` 与 `tag`
- 自动创建中文提交和本地插件级 tag
- 不自动 push，不创建 PR 或 GitHub Release

## Core 发布脚本

仓库内提供 core 专用升版脚本：

```bash
./scripts/release/ak-core-release.sh patch
./scripts/release/ak-core-release.sh minor
./scripts/release/ak-core-release.sh major
```

底层实现仍然保留为：

```bash
uv run python scripts/release/release_core.py patch
uv run python scripts/release/release_core.py minor
uv run python scripts/release/release_core.py major
```

第一版行为固定为：

- 优先推荐使用 `./scripts/release/ak-core-release.sh`
- 只处理 core `agent-kit` 自身版本
- 参数缺失或错误时，会直接输出用法和可用版本类型提示
- 自动更新根 `pyproject.toml` 与 `src/agent_kit/__init__.py` 中的版本号
- 自动执行 `uv lock`，并在有变化时把 `uv.lock` 纳入同一次发布提交
- 自动创建中文提交和本地 core tag，tag 格式为 `v<version>`
- 不自动 push，不创建 PR 或 GitHub Release

## 目录说明

- [src/agent_kit](src/agent_kit)：core 实现
- [packages](packages)：所有插件目录
- [scripts](scripts)：开发与发布辅助脚本
- [registry/official.json](registry/official.json)：仓库内官方注册表
- [src/agent_kit/official_registry.json](src/agent_kit/official_registry.json)：打包内置注册表副本
- [tests](tests)：core 测试
