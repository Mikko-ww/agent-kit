# Zsh 命令补全功能可行性调研

## 摘要

当前 `agent-kit` CLI 在所有 Typer 实例上显式禁用了补全功能（`add_completion=False`），导致用户在 Zsh（包括 oh-my-zsh）中无法获得命令和选项的 Tab 补全提示。本文档调研在 Zsh 环境下为 `agent-kit` 及其插件命令添加补全功能的可行方案，并给出推荐方案与实施路径。

## 背景

### 现状

`agent-kit` 基于 [Typer](https://typer.tiangolo.com/)（底层为 Click）构建 CLI，入口命令为 `agent-kit`，别名为 `ak`。当前 CLI 结构如下：

```
agent-kit
├── --version / -V               # 版本信息
├── plugins                      # 插件管理子命令组
│   ├── refresh                  # 刷新插件注册表
│   ├── list                     # 列出所有插件
│   ├── info <plugin_id>         # 查看插件详情
│   ├── install <plugin_id>      # 安装插件
│   ├── update <plugin_id>       # 更新插件
│   └── remove <plugin_id>       # 卸载插件
├── config                       # 全局配置子命令组
│   ├── get <key>                # 获取配置项
│   ├── list                     # 列出配置项
│   └── set <key> <value>        # 设置配置项
├── alias                        # 别名管理子命令组
│   ├── enable                   # 启用 ak 别名
│   ├── disable                  # 禁用 ak 别名
│   └── status                   # 查看别名状态
├── skills-link (sl)             # 第一方插件（动态注册）
├── opencode-env-switch (oes)    # 第一方插件（动态注册）
└── self-evolve (se)             # 第一方插件（动态注册）
```

### 当前代码中补全被禁用的位置

在 `src/agent_kit/cli.py` 中：

```python
# 主应用
app = typer.Typer(
    ...,
    add_completion=False,   # 行 43
)

# 子命令组
plugins_app = typer.Typer(..., add_completion=False)   # 行 60
config_app = typer.Typer(..., add_completion=False)     # 行 61
alias_app = typer.Typer(..., add_completion=False)      # 行 62
```

### 问题

1. 用户输入 `agent-kit ` 后按 Tab 无补全建议
2. 用户输入 `agent-kit plugins ` 后按 Tab 无子命令补全
3. 插件命令（如 `agent-kit skills-link`）及其别名（如 `agent-kit sl`）无法补全
4. `--version`、`--purge-config` 等选项无法补全
5. `ak` 别名同样无法获得补全

### 补全的特殊挑战

`agent-kit` 的命令结构存在以下特殊性，使得补全方案必须妥善处理：

- **动态插件子命令**：插件通过 `PluginManager.runnable_plugins()` 在运行时发现并注册为顶层子命令，不同用户安装了不同的插件
- **插件别名**：每个第一方插件有一个缩写别名（如 `sl` → `skills-link`），别名作为隐藏命令注册
- **插件透传参数**：插件子命令使用 `allow_extra_args=True` 和 `ignore_unknown_options=True`，参数直接透传给插件进程
- **`ak` 别名**：`ak` 是一个独立的 shell wrapper 脚本（`exec agent-kit "$@"`），补全需要同时覆盖 `agent-kit` 和 `ak` 两个命令名

## 方案对比

### 方案一：启用 Typer/Click 内置补全机制

#### 原理

Typer 基于 Click 提供了开箱即用的 Shell 补全支持。核心机制是：

1. 将 `add_completion=True`（或删除该参数使用默认值），Typer 会自动注册 `--install-completion` 和 `--show-completion` 两个选项
2. 用户执行 `agent-kit --install-completion` 后，Typer 自动向 `~/.zshrc` 写入一行形如：

   ```zsh
   eval "$(_AGENT_KIT_COMPLETE=zsh_source agent-kit)"
   ```

3. 之后每次启动 Zsh 时，shell 会调用 `agent-kit` 并设置 `_AGENT_KIT_COMPLETE=zsh_source` 环境变量，Typer/Click 据此输出补全脚本
4. 当用户按 Tab 时，shell 再次调用 `agent-kit` 并设置 `_AGENT_KIT_COMPLETE=zsh_complete`，Typer/Click 据此输出候选项

#### 改动范围

- 移除所有 `add_completion=False` 参数
- 无需引入新依赖

#### 优点

- **改动极小**：仅需移除 4 处 `add_completion=False`
- **零额外维护**：Typer/Click 内置维护，随框架升级自动兼容
- **自动覆盖动态子命令**：因为补全时会实际执行 `agent-kit`，所有运行时注册的插件命令和别名都能被发现
- **跨 Shell 支持**：同时支持 Bash、Zsh、Fish、PowerShell

#### 缺点

- **启动开销**：每次补全查询都会触发 Python 解释器和 `agent-kit` 的 `create_app()` 流程，包括插件发现，可能有 0.2–0.5 秒延迟
- **oh-my-zsh 集成不自然**：`--install-completion` 直接修改 `~/.zshrc`，不走 oh-my-zsh 的插件/自定义补全体系
- **`ak` 别名无法自动覆盖**：内置机制仅为 `agent-kit` 注册补全，`ak` 别名需要额外的 `compdef _agent-kit ak` 补充
- **环境变量命名**：Typer 会将 `agent-kit` 转为 `_AGENT_KIT_COMPLETE`，需要确认带连字符的命令名转换逻辑正确

#### 可行性评估

**可行**。这是改动最小的方案，但用户体验略粗糙（补全略有延迟，oh-my-zsh 集成不够自然）。

---

### 方案二：自定义 oh-my-zsh 插件

#### 原理

创建标准的 oh-my-zsh 自定义插件目录结构，内含 Zsh 补全函数：

```
~/.oh-my-zsh/custom/plugins/agent-kit/
├── _agent-kit               # Zsh 补全函数文件
└── agent-kit.plugin.zsh     # oh-my-zsh 插件入口
```

#### 补全函数设计

`_agent-kit` 文件使用 Zsh 的 `_arguments` 或 `_describe` 编写静态补全逻辑，或者内部调用 `agent-kit` 动态获取补全信息。

#### 分发方式

通过 `agent-kit` 新增子命令（如 `agent-kit completion install`）或与现有 `alias enable` 流程整合，将插件文件安装到用户系统。

#### 优点

- **oh-my-zsh 原生体验**：用户只需在 `plugins=(...)` 中加入 `agent-kit` 即可启用
- **可同时覆盖 `agent-kit` 和 `ak`**：在 `agent-kit.plugin.zsh` 中一并注册
- **可控的分发流程**：与现有 `alias` 管理模块设计思路一致

#### 缺点

- **仅支持 oh-my-zsh 用户**：原生 Zsh 用户或使用 Prezto、zinit 等框架的用户需要另外的安装方式
- **需要维护 Zsh 脚本**：每次新增核心子命令都需同步更新补全脚本
- **静态补全无法自动发现动态插件**：除非内部调用 `agent-kit` 获取插件列表

#### 可行性评估

**可行但场景受限**。适合作为方案三的子集补充，不适合作为唯一方案。

---

### 方案三：混合方案（推荐）

#### 原理

结合 Typer/Click 内置动态补全能力和 oh-my-zsh 插件分发形式：

1. **启用 Typer/Click 内置补全引擎**：移除 `add_completion=False`，让 Typer/Click 的补全运行时成为实际的补全数据源
2. **提供 `agent-kit completion` 子命令组**：
   - `agent-kit completion install [--shell zsh]`：安装补全脚本到合适的位置
   - `agent-kit completion show [--shell zsh]`：输出补全脚本内容
   - `agent-kit completion remove [--shell zsh]`：卸载已安装的补全
3. **支持多种安装位置**：
   - oh-my-zsh 自定义插件目录（优先检测）
   - Zsh 标准 `fpath` 目录
   - 直接写入 `~/.zshrc`
4. **ak 别名自动补全**：生成的补全脚本自动包含 `compdef _agent-kit ak`

#### 补全脚本内容

生成的补全脚本本质上仍然调用 Typer/Click 的内置补全机制，但包装为标准 Zsh 补全格式：

```zsh
#compdef agent-kit ak

# agent-kit managed completion
_agent-kit() {
    eval "$(COMP_WORDS="${words[*]}" \
            COMP_CWORD=$((CURRENT-1)) \
            _AGENT_KIT_COMPLETE=zsh_complete \
            agent-kit)"
}

compdef _agent-kit agent-kit
compdef _agent-kit ak
```

#### oh-my-zsh 插件安装方式

当检测到 oh-my-zsh 环境时，安装命令将文件写入：

```
~/.oh-my-zsh/custom/plugins/agent-kit/
├── _agent-kit                  # 补全函数
└── agent-kit.plugin.zsh        # fpath 注册 + compdef
```

`agent-kit.plugin.zsh` 内容：

```zsh
# agent-kit managed completion plugin
fpath=($fpath ${0:A:h})
compdef _agent-kit agent-kit
compdef _agent-kit ak
```

#### 非 oh-my-zsh 安装方式

当未检测到 oh-my-zsh 时，安装命令将补全脚本写入标准位置（如 `~/.zfunc/_agent-kit`），并在 `~/.zshrc` 中添加：

```zsh
fpath=(~/.zfunc $fpath)
autoload -Uz compinit && compinit
```

#### CLI 新增命令

```
agent-kit completion
├── install [--shell zsh|bash|fish]   # 安装补全
├── show [--shell zsh|bash|fish]      # 显示补全脚本
└── remove [--shell zsh|bash|fish]    # 卸载补全
```

#### 优点

- **动态补全完整性**：所有核心命令、动态插件命令、插件别名都能被补全
- **oh-my-zsh 原生集成**：自动检测并使用 oh-my-zsh 插件体系
- **覆盖 `ak` 别名**：补全脚本自动覆盖
- **可扩展性**：未来可轻松扩展到 Bash 和 Fish
- **符合 `agent-kit` 的管理风格**：与现有 `alias enable/disable/status` 模式一致

#### 缺点

- **实现工作量较大**：需要新增 `completion` 子命令组、shell 检测逻辑、文件管理逻辑
- **补全仍有启动延迟**：底层仍依赖 Typer/Click 的动态补全，需要启动 Python 进程

#### 可行性评估

**推荐方案。** 在保持最小改动的同时提供最佳用户体验，且与现有 `alias` 管理模块设计思路一致。

---

### 方案四：纯静态 Zsh 补全脚本

#### 原理

手工编写完整的 Zsh 补全函数 `_agent-kit`，使用 `_arguments`、`_describe` 等 Zsh 原生补全工具，硬编码所有已知命令和选项。

#### 优点

- **零启动延迟**：纯 shell 脚本，不需要启动 Python
- **离线可用**：不依赖 `agent-kit` 可执行文件

#### 缺点

- **无法补全动态插件命令**：用户安装的插件无法自动出现在补全列表中
- **维护成本高**：每次新增或修改命令都需同步更新 Zsh 脚本
- **与 `agent-kit` 架构不匹配**：项目的核心价值在于插件可扩展性，纯静态补全与此矛盾

#### 可行性评估

**不推荐。** 与项目动态插件架构存在根本矛盾。

## 方案对比总结

| 维度 | 方案一（Typer 内置） | 方案二（oh-my-zsh 插件） | 方案三（混合方案） | 方案四（纯静态脚本） |
|------|---------------------|------------------------|-------------------|-------------------|
| 改动量 | 极小（4 处移除） | 中等 | 较大 | 中等 |
| 动态插件支持 | ✅ 自动 | ⚠️ 需手动更新或动态调用 | ✅ 自动 | ❌ 不支持 |
| oh-my-zsh 集成 | ❌ 写入 `.zshrc` | ✅ 原生 | ✅ 原生 | ⚠️ 需手动配置 |
| `ak` 别名覆盖 | ❌ 需额外处理 | ✅ 支持 | ✅ 支持 | ✅ 支持 |
| 补全延迟 | 0.2–0.5s | 取决于实现 | 0.2–0.5s | 零延迟 |
| 跨 Shell 支持 | ✅ 自动 | ❌ 仅 Zsh | ✅ 可扩展 | ❌ 仅 Zsh |
| 维护成本 | 极低 | 中等 | 低 | 高 |
| 卸载管理 | ❌ 需手动清理 | ⚠️ 需手动删除 | ✅ 内置命令 | ❌ 需手动清理 |

## 推荐方案

**推荐方案三：混合方案**，理由如下：

1. **与项目架构一致**：动态补全能自动发现运行时注册的插件命令，契合 `agent-kit` 可扩展插件架构的核心设计
2. **与现有模块风格一致**：`completion install/remove/show` 与现有 `alias enable/disable/status` 的管理风格统一
3. **覆盖核心用户场景**：oh-my-zsh 是 Zsh 用户中使用最广泛的框架，优先支持其插件体系能覆盖大多数用户
4. **可迭代扩展**：首期只实现 Zsh 支持，后续可扩展至 Bash 和 Fish

## 实施路径

### 第一阶段：启用补全引擎

1. 移除 `src/agent_kit/cli.py` 中所有 `add_completion=False`
2. 但同时隐藏 Typer 默认注入的 `--install-completion` 和 `--show-completion`，改由自定义 `completion` 子命令管理
3. 验证 `_AGENT_KIT_COMPLETE=zsh_complete agent-kit` 能正确输出候选项

### 第二阶段：新增 `completion` 子命令组

1. 新增 `src/agent_kit/completion.py` 模块，封装：
   - Shell 类型检测（Zsh/Bash/Fish）
   - oh-my-zsh 环境检测（检查 `$ZSH_CUSTOM` 或 `~/.oh-my-zsh/custom`）
   - 补全脚本生成（基于 Typer/Click 的 `zsh_source` 输出包装）
   - 文件安装/卸载逻辑
2. 在 `cli.py` 中注册 `completion` 子命令组
3. 更新 `RESERVED_COMMAND_NAMES` 加入 `"completion"`

### 第三阶段：补全脚本与安装逻辑

1. 实现 oh-my-zsh 插件安装路径：
   - 检测 `$ZSH_CUSTOM` 环境变量
   - 在 `$ZSH_CUSTOM/plugins/agent-kit/` 下写入 `_agent-kit` 和 `agent-kit.plugin.zsh`
   - 提示用户在 `~/.zshrc` 的 `plugins=(...)` 中添加 `agent-kit`
2. 实现标准 Zsh 安装路径：
   - 将补全脚本写入 `~/.zfunc/_agent-kit`
   - 添加 `fpath` 配置到 `~/.zshrc`
3. 在补全脚本中自动包含 `compdef _agent-kit ak`

### 第四阶段：测试与文档

1. 单元测试：
   - 补全脚本生成内容的正确性
   - oh-my-zsh 环境检测逻辑
   - 安装/卸载文件操作
   - `ak` 别名补全注册
2. 更新 `README.md` 说明补全安装方式
3. 更新 `AGENTS.md` 记录 `completion` 子命令

## 文件影响范围

预期需要新增或修改的文件：

- `src/agent_kit/cli.py`：移除 `add_completion=False`，注册 `completion` 子命令组
- `src/agent_kit/completion.py`（新增）：补全管理核心逻辑
- `src/agent_kit/messages.py`（或语言文件）：新增 `completion` 相关翻译键
- `tests/test_completion.py`（新增）：补全功能测试
- `README.md`：补全安装说明
- `src/agent_kit/AGENTS.md`：记录新模块

## 参考资料

- [Click Shell Completion 文档](https://click.palletsprojects.com/en/stable/shell-completion/)
- [Typer 自动补全教程](https://typer.tiangolo.com/tutorial/options-autocompletion/)
- [Typer Shell Completion 内部机制](https://deepwiki.com/fastapi/typer/4-shell-completion)（非官方资料，仅供补充参考）
- [oh-my-zsh 自定义插件指南](https://github.com/ohmyzsh/ohmyzsh/wiki/Customization)
- [oh-my-zsh 外部插件规范](https://github.com/ohmyzsh/ohmyzsh/wiki/External-plugins)
- [zsh-completions 项目](https://github.com/zsh-users/zsh-completions)
- [argcomplete 文档](https://kislyuk.github.io/argcomplete/)（argparse 生态的 Zsh 补全方案，本项目使用 Typer/Click 故不适用，仅作技术对比参考）
- [shtab 文档](https://github.com/iterative/shtab)（argparse 生态的静态补全脚本生成工具，仅作技术对比参考）
