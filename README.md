# agent-kit

`agent-kit` 是一个可扩展的 Python CLI 平台，统一入口是 `agent-kit`。

## 项目概览

- Core 负责官方插件注册表、插件安装/更新/卸载、版本校验和命令转发。
- 插件运行在各自独立环境中，core 通过子进程调用统一入口 `agent-kit-plugin`。
- 当前第一方插件是 [packages/skills-link](packages/skills-link)，用于把本地 skills 目录按目录粒度链接到目标目录。

## 插件安装模型

用户安装官方插件的入口固定是：

```bash
agent-kit plugins install <plugin-id>
```

当前 core 支持三种官方来源：

- `pypi`：从包索引安装指定分发包版本。
- `git`：从 Git 仓库的固定 `commit` 安装，可带 `subdirectory`。
- `wheel`：从远程 `.whl` 制品安装。

`wheel` 来源的规则：

- 只支持远程 `.whl`，不支持本地路径，也不支持源码包。
- 安装前会先把制品下载到缓存目录。
- 下载完成后必须先做 `sha256` 校验。
- 校验通过后，才会从本地缓存的 wheel 安装到插件独立环境。
- 安装完成后仍会继续校验 `plugin_id`、`installed_version`、`api_version`、分发包名和分发包版本。

当前仓库已经具备 `wheel` 安装能力，但官方内置插件条目暂未切换到 `wheel`。目前内置的 `skills-link` 仍然使用 `git` 来源。

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
agent-kit plugins list
agent-kit plugins info skills-link
agent-kit plugins install skills-link
agent-kit skills-link status
```

## 目录说明

- [src/agent_kit](src/agent_kit)：core 实现
- [packages](packages)：所有插件目录
- [registry/official.json](registry/official.json)：仓库内官方注册表
- [src/agent_kit/official_registry.json](src/agent_kit/official_registry.json)：打包内置注册表副本
- [tests](tests)：core 测试
