# Wheel 插件安装 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `agent-kit` 新增官方插件远程 `.whl` 安装模式，保留现有 `pypi` 与 `git` 语义，并在安装前完成 `sha256` 强校验。

**Architecture:** 扩展注册表来源类型为 `pypi | git | wheel`。当条目是 `wheel` 时，core 先把远程 wheel 下载到缓存目录，校验 `sha256`，再从本地 wheel 安装到插件独立环境中；安装后继续复用现有的插件元数据和分发元数据校验链路。当前官方注册表中的 `skills-link` 条目暂不切换到 `wheel`，实现先支持能力本身。

**Tech Stack:** Python 3.11, uv, Typer, pytest, hashlib, urllib.request

---

## Chunk 1: 注册表与数据模型扩展

### Task 1: 为 `wheel` 来源补齐红测

**Files:**
- Modify: `tests/test_plugin_manager.py`

- [ ] **Step 1: 为注册表字段解析写失败测试**

在 `tests/test_plugin_manager.py` 新增一个测试，构造 `source_type = "wheel"` 的条目，并断言 `RegistryPlugin.from_dict(...)` 能读取：

```python
{
    "plugin_id": "skills-link",
    "source_type": "wheel",
    "package_name": "skills-link",
    "version": "0.2.0",
    "wheel_url": "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl",
    "sha256": "abc123",
    "api_version": 1,
    "min_core_version": "0.1.0",
}
```

- [ ] **Step 2: 为 `install_spec()` 写失败测试**

在同一个测试文件中新增断言：

```python
entry.install_spec() == "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl"
```

- [ ] **Step 3: 运行精确测试确认先失败**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -k wheel -v
```

Expected:

- FAIL
- 失败原因是 `RegistryPlugin` 还不支持 `wheel_url` / `sha256` 或 `install_spec()` 还不支持 `wheel`

### Task 2: 扩展注册表模型

**Files:**
- Modify: `src/agent_kit/registry.py`

- [ ] **Step 1: 给 `RegistryPlugin` 增加字段**

在 `RegistryPlugin` 中新增：

```python
wheel_url: str | None = None
sha256: str | None = None
```

- [ ] **Step 2: 在 `from_dict()` 中解析新字段**

把 `wheel_url` 和 `sha256` 加入 `from_dict()` 的构造流程，仍使用现有 `_optional_str(...)` 风格。

- [ ] **Step 3: 在 `install_spec()` 中支持 `wheel`**

新增一个分支：

```python
if self.source_type == "wheel":
    if not self.wheel_url or not self.sha256 or not self.package_name:
        raise ValueError(...)
    return self.wheel_url
```

- [ ] **Step 4: 跑精确测试确认转绿**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -k wheel -v
```

Expected:

- PASS

### Task 3: 为安装态新增 `source_sha256`

**Files:**
- Modify: `src/agent_kit/plugin_manager.py`
- Test: `tests/test_plugin_manager.py`

- [ ] **Step 1: 为 `InstalledPluginRecord` 补失败测试**

在 `tests/test_plugin_manager.py` 新增一个针对 `plugin.json` 的断言，要求 `wheel` 安装成功后记录：

```python
record.source_type == "wheel"
record.source_ref == "https://example.com/releases/skills_link-0.2.0-py3-none-any.whl"
record.source_sha256 == "abc123"
```

- [ ] **Step 2: 扩展 `InstalledPluginRecord`**

在 `src/agent_kit/plugin_manager.py` 给 `InstalledPluginRecord` 增加：

```python
source_sha256: str | None = None
```

并同步更新 `from_dict(...)`。

- [ ] **Step 3: 让 `_write_record()` 和 `_load_record()` 支持新字段**

保持 JSON 兼容：

- 老记录没有 `source_sha256` 时，读取结果应为 `None`
- 新记录写入时应包含该字段

- [ ] **Step 4: 运行目标测试**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -k "source_sha256 or wheel" -v
```

Expected:

- PASS

## Chunk 2: Wheel 下载、校验与安装链路

### Task 4: 扩展缓存路径布局

**Files:**
- Modify: `src/agent_kit/paths.py`
- Test: `tests/test_plugin_manager.py`

- [ ] **Step 1: 为缓存目录路径补失败测试**

在 `tests/test_plugin_manager.py` 新增断言，要求 `AgentKitLayout` 能生成：

```python
layout.cache_root / "artifacts" / "skills-link"
```

以及具体 wheel 文件路径。

- [ ] **Step 2: 在 `paths.py` 新增 helper**

新增：

```python
def plugin_artifact_dir(self, plugin_id: str) -> Path: ...
def plugin_artifact_path(self, plugin_id: str, filename: str) -> Path: ...
```

- [ ] **Step 3: 跑目标测试**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -k artifact -v
```

Expected:

- PASS

### Task 5: 为 wheel 下载与 hash 校验写失败测试

**Files:**
- Modify: `tests/test_plugin_manager.py`

- [ ] **Step 1: 为 wheel 成功安装写失败测试**

新增一个 `source_type = "wheel"` 的安装测试，要求：

- 先下载 wheel 到缓存目录
- 校验 `sha256`
- 再执行安装
- 最终写入 `source_ref` 和 `source_sha256`

建议通过 monkeypatch / stub 注入：

- `manager.download_artifact = ...`
- `manager.hash_artifact = ...`
- `manager.command_runner = ...`
- `manager.probe_plugin_metadata = ...`
- `manager.probe_distribution_metadata = ...`

- [ ] **Step 2: 为缓存复用写失败测试**

新增一个测试，要求：

- wheel 已存在
- `hash_artifact(...)` 返回与注册表一致
- 不再触发重新下载

- [ ] **Step 3: 为 hash 失败写失败测试**

新增一个测试，要求：

- 下载成功
- `hash_artifact(...)` 与注册表中的 `sha256` 不一致
- 直接抛出 `PluginError`
- 不执行 `uv pip install`

- [ ] **Step 4: 运行目标测试确认红灯**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -k "wheel and (install or hash or artifact)" -v
```

Expected:

- FAIL

### Task 6: 实现 wheel 下载与校验逻辑

**Files:**
- Modify: `src/agent_kit/plugin_manager.py`

- [ ] **Step 1: 引入可注入的下载与 hash helper**

在 `PluginManager` 中新增默认 helper，并允许测试替换：

```python
self.download_artifact = ...
self.hash_artifact = ...
```

默认实现建议：

- `download_artifact(url: str, destination: Path) -> Path`
- `hash_artifact(path: Path) -> str`

- [ ] **Step 2: 在 `install_plugin()` 中识别 `wheel`**

在真正安装前分支处理：

- 若是 `wheel`，先解析文件名
- 落到 `layout.plugin_artifact_dir(plugin_id)`
- 下载或复用缓存文件
- 做 `sha256` 校验
- 校验通过后，把本地 wheel 路径传给安装步骤

- [ ] **Step 3: 调整 `_install_distribution()`**

将 `_install_distribution()` 改成支持传入一个明确安装目标，例如：

```python
def _install_distribution(self, plugin_id: str, install_target: str) -> None:
    ...
```

其中：

- `pypi` / `git` 仍然传 `entry.install_spec()`
- `wheel` 传本地 wheel 文件路径

- [ ] **Step 4: 仅对 wheel 做 hash 校验**

确保：

- `pypi` / `git` 逻辑不变
- `wheel` 若 hash 不一致则抛 `PluginError`
- hash 失败后不执行安装

- [ ] **Step 5: 保留现有安装后校验**

不要删除现有：

- `probe_plugin_metadata(...)`
- `probe_distribution_metadata(...)`
- `_verify_installation(...)`

对 `wheel` 来说，安装后继续校验：

- `plugin_id`
- `api_version`
- `package_name`
- `version`

注意：

- 不要尝试把 `direct_url.json` 里的本地 `file://...` 与远程 `wheel_url` 做强比较，因为安装源已经变成本地缓存文件

- [ ] **Step 6: 在成功记录里写入 `source_sha256`**

当 `source_type = "wheel"` 时：

```python
source_ref = entry.wheel_url
source_sha256 = entry.sha256
```

其它来源：

- `source_ref` 维持现状
- `source_sha256 = None`

- [ ] **Step 7: 跑针对性测试**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -k "wheel or artifact or hash" -v
```

Expected:

- PASS

### Task 7: 为更新行为补最小测试

**Files:**
- Modify: `tests/test_plugin_manager.py`

- [ ] **Step 1: 为 `update_plugin()` 的 wheel 重新安装行为补测试**

新增一个测试，断言：

- `update_plugin("skills-link")` 会重新走当前有效注册表条目
- 当条目中的 `version` / `wheel_url` / `sha256` 发生变化时，最终写出的记录以新条目为准

- [ ] **Step 2: 运行目标测试**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -k "update and wheel" -v
```

Expected:

- PASS

## Chunk 3: 文档与回归验证

### Task 8: 更新 README 与 AGENTS 文档

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `src/agent_kit/AGENTS.md`

- [ ] **Step 1: 更新 `README.md`**

最少补充：

- 当前插件安装来源支持 `pypi`、`git`、`wheel`
- `wheel` 只支持远程 `.whl`
- `wheel` 安装会先下载、校验 `sha256`，再安装
- 当前官方插件条目若仍未切换到 `wheel`，要明确说明

- [ ] **Step 2: 更新根目录 `AGENTS.md`**

若本次实现引入新的核心安装能力，在根目录摘要中确认无需新增过多细节；只在必要时补一条“支持 `wheel` 安装模式”的摘要说明。

- [ ] **Step 3: 更新 `src/agent_kit/AGENTS.md`**

补充 core 安装来源说明：

- 注册表来源现在支持 `pypi | git | wheel`
- `wheel` 来源需要下载、缓存和 `sha256` 校验

- [ ] **Step 4: 检查文档路径仍为相对路径**

Run:

```bash
rg -n "/Users/|\\]\\(/" README.md AGENTS.md src/agent_kit/AGENTS.md || true
```

Expected:

- 无输出

### Task 9: 全量验证

**Files:**
- Verify: `tests/test_plugin_manager.py`
- Verify: `README.md`
- Verify: `src/agent_kit/registry.py`
- Verify: `src/agent_kit/plugin_manager.py`
- Verify: `src/agent_kit/paths.py`

- [ ] **Step 1: 跑插件管理器测试**

Run:

```bash
uv run pytest tests/test_plugin_manager.py -v
```

Expected:

- PASS

- [ ] **Step 2: 跑全量测试**

Run:

```bash
uv run pytest
```

Expected:

- PASS

- [ ] **Step 3: 做一个最小 CLI smoke check**

Run:

```bash
uv run agent-kit plugins list
uv run agent-kit plugins info skills-link
```

Expected:

- CLI 正常输出
- 不因为 `wheel` 支持的引入而破坏已有命令

- [ ] **Step 4: 提交**

Run:

```bash
git add src/agent_kit/registry.py src/agent_kit/plugin_manager.py src/agent_kit/paths.py tests/test_plugin_manager.py README.md AGENTS.md src/agent_kit/AGENTS.md
git commit -m "支持 wheel 插件安装模式"
```

Expected:

- 提交成功
- 提交信息为中文

## 实施备注

- 当前官方注册表中的 `skills-link` 条目没有真实可用的远程 wheel URL，本计划默认先实现能力，不在本轮强制把注册表切换到 `wheel`
- 如果后续要真正把某个官方插件条目切换到 `wheel`，必须额外准备：
  - 可访问的远程 `.whl`
  - 对应 `sha256`
  - 更新后的官方注册表条目
