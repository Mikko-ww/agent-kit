# Wheel 插件安装设计

## 摘要

当前 `agent-kit` 的插件安装来源支持两种类型：

- `pypi`
- `git`

但当前官方插件注册表中的实际插件 `skills-link` 只使用 `git` 来源。为了让官方插件支持更稳定、可控的成品分发，本设计新增第三种安装来源：

- `wheel`

该来源仅支持远程 `.whl` 制品，不支持本地文件路径，不支持源码包。用户入口保持不变，仍然通过：

- `agent-kit plugins install <plugin-id>`

实际安装来源由官方注册表条目决定。

## 目标

- 在保持现有命令模型不变的前提下，支持官方插件通过远程 wheel 安装
- 继续保持“只允许安装官方注册表中的插件”这一边界
- 对远程 wheel 做强校验，避免下载内容被篡改或与注册表声明不一致
- 保留现有插件元数据与分发元数据校验链路

## 非目标

- 不支持用户直接传入任意 URL 安装插件
- 不支持本地 wheel 路径安装
- 不支持 `sdist`、`.tar.gz`、`.zip` 等源码包
- 不改变现有 `pypi` 与 `git` 来源的语义

## 用户视角

用户入口不变：

- `agent-kit plugins install skills-link`
- `agent-kit plugins update skills-link`

变化只发生在内部实现：当官方注册表中某个插件的 `source_type` 为 `wheel` 时，core 将下载远程 wheel、校验 hash，再从本地缓存 wheel 完成安装。

## 现状

当前实现位置：

- 注册表模型：[src/agent_kit/registry.py](src/agent_kit/registry.py)
- 插件安装流程：[src/agent_kit/plugin_manager.py](src/agent_kit/plugin_manager.py)
- 官方注册表副本：
  - [registry/official.json](registry/official.json)
  - [src/agent_kit/official_registry.json](src/agent_kit/official_registry.json)

当前 `RegistryPlugin.install_spec()` 仅支持：

- `pypi -> package_name==version`
- `git -> git+url@commit#subdirectory=...`

## 设计概览

### 新增来源类型

`RegistryPlugin.source_type` 新增第三种取值：

- `wheel`

完整支持范围变为：

- `pypi`
- `git`
- `wheel`

### 注册表新增字段

当 `source_type = "wheel"` 时，注册表条目必须包含：

- `package_name`
- `version`
- `wheel_url`
- `sha256`
- `api_version`
- `min_core_version`

示例：

```json
{
  "plugin_id": "skills-link",
  "display_name": "Skills Link",
  "description": "Link selected local skills into a target directory.",
  "source_type": "wheel",
  "package_name": "skills-link",
  "version": "0.1.0",
  "wheel_url": "https://example.com/releases/skills_link-0.1.0-py3-none-any.whl",
  "sha256": "abc123...",
  "api_version": 1,
  "min_core_version": "0.1.0"
}
```

### RegistryPlugin 变更

`RegistryPlugin` 新增字段：

- `wheel_url: str | None`
- `sha256: str | None`

`install_spec()` 新增逻辑：

- 当 `source_type == "wheel"` 时，返回 `wheel_url`

## 安装流程

### 通用前置流程

无论来源类型如何，安装流程前半段保持不变：

1. 从有效注册表中按 `plugin_id` 取条目
2. 校验该插件是否属于官方注册表
3. 校验 `min_core_version`
4. 创建插件数据目录
5. 创建插件独立虚拟环境

### Wheel 安装专属流程

当 `source_type = "wheel"` 时，安装流程改为：

1. 根据注册表中的 `wheel_url` 解析出文件名
2. 将 wheel 下载到缓存目录：
   - `~/.cache/agent-kit/artifacts/<plugin-id>/`
3. 对下载后的文件计算 `sha256`
4. 与注册表中的 `sha256` 比较
5. 校验通过后，执行：

```bash
uv pip install --python <venv_python> <local_wheel_path>
```

6. 安装完成后，继续走现有插件元数据与分发元数据校验

### 为什么不直接用远程 URL 安装

不建议直接把远程 URL 交给 `uv pip install`，原因是：

- 无法在安装前做独立 hash 校验
- 排障时缺少本地缓存文件
- 难以明确区分“下载失败”、“hash 失败”、“安装失败”
- 后续若做制品缓存复用，缺少清晰落点

## 缓存设计

新增制品缓存目录：

- `~/.cache/agent-kit/artifacts/<plugin-id>/`

文件命名规则：

- 默认使用 `wheel_url` 中的文件名

复用逻辑：

- 若目标文件已存在，则先重新计算 `sha256`
- 若与注册表中的 `sha256` 一致，则直接复用
- 若不一致，则删除旧文件并重新下载

## 安装后校验

### 保留现有校验

wheel 安装完成后，仍然保留当前已有的两层校验：

1. 插件运行时元数据校验
   - 调用 `agent-kit-plugin --plugin-metadata`
   - 校验：
     - `plugin_id`
     - `installed_version`
     - `api_version`
     - `config_version`

2. 分发包元数据校验
   - 使用插件环境内的 Python 读取 `importlib.metadata`
   - 校验：
     - `package_name`
     - `version`

### 新增 wheel 来源校验

wheel 来源必须增加：

- 下载文件的 `sha256` 校验

必要时，安装态中还应保存该次安装的 `wheel_url` 与 `sha256`，便于 `plugins info` 与排障。

## plugin.json 变更

当前安装态文件：

- `~/.local/share/agent-kit/plugins/<plugin-id>/plugin.json`

现有字段保持不变，并对 `wheel` 来源新增记录：

- `source_type = "wheel"`
- `source_ref = wheel_url`
- `source_sha256 = sha256`

目的：

- 让安装来源可审计
- 支持后续 `plugins info`
- 为未来的更新判断和排障提供依据

## 更新策略

更新命令保持不变：

- `agent-kit plugins update <plugin-id>`

更新判断规则：

- 完全以当前有效注册表条目为准

对 `wheel` 来源，若以下任一项变化，则触发重新安装：

- `version`
- `wheel_url`
- `sha256`

不额外对远程 URL 做独立“最新版本探测”。

## 错误处理

### 下载阶段错误

需要清晰区分：

- URL 不可访问
- 下载超时
- 下载内容为空
- URL 对应文件名无效

### Hash 校验错误

若 `sha256` 不匹配：

- 立即中止安装
- 不继续执行 `uv pip install`
- 删除本次下载的临时文件
- 报错信息中明确指出是 hash 校验失败

### 安装后校验错误

若元数据不匹配：

- 与现有安装流程保持一致
- 回滚删除该插件的数据目录
- 不留下半安装状态

## 兼容性

### 对现有来源的兼容性

- `pypi` 逻辑保持不变
- `git` 逻辑保持不变
- 仅新增 `wheel` 分支，不修改原有语义

### 对用户命令的兼容性

命令不变：

- `agent-kit plugins install <plugin-id>`
- `agent-kit plugins update <plugin-id>`
- `agent-kit plugins info <plugin-id>`

### 对文档的影响

若实现该设计，需要同步检查并更新：

- 根目录 `README.md`
- 与插件安装来源相关的说明文档
- 涉及安装模式的 `AGENTS.md`

## 测试计划

### 注册表测试

新增测试覆盖：

- `RegistryPlugin` 能解析 `wheel_url` 与 `sha256`
- `install_spec()` 在 `wheel` 来源下返回 `wheel_url`

### 安装流程测试

新增测试覆盖：

- wheel 文件下载成功
- 已有缓存文件且 hash 一致时复用
- 已有缓存文件但 hash 不一致时重下
- `sha256` 校验失败时中止安装
- wheel 安装成功后记录 `source_ref` 与 `source_sha256`
- 安装后插件元数据或分发元数据不匹配时正确回滚

### 更新流程测试

新增测试覆盖：

- `version` 变化时重新安装
- `wheel_url` 变化时重新安装
- `sha256` 变化时重新安装

### CLI 测试

需要确认：

- `plugins list` 与 `plugins info` 对 `wheel` 来源信息展示正确

## 文件影响范围

预期需要修改的核心文件：

- [src/agent_kit/registry.py](src/agent_kit/registry.py)
- [src/agent_kit/plugin_manager.py](src/agent_kit/plugin_manager.py)
- [src/agent_kit/paths.py](src/agent_kit/paths.py)
- [tests/test_plugin_manager.py](tests/test_plugin_manager.py)
- [registry/official.json](registry/official.json)
- [src/agent_kit/official_registry.json](src/agent_kit/official_registry.json)
- [README.md](README.md)

## 验收标准

- 注册表可以合法声明 `wheel` 来源插件
- `agent-kit plugins install <plugin-id>` 能从远程 `.whl` 成功安装插件
- 安装前会执行 `sha256` 校验
- 安装后仍保留现有元数据与版本校验
- `plugin.json` 能记录 `wheel_url` 与 `sha256`
- `update` 行为完全由有效注册表条目驱动
- 不支持本地路径和源码包
