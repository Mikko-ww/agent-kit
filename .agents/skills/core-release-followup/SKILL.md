---
name: core-release-followup
description: 当在 agent-kit 仓库中修改任意非插件目录文件并准备提交，或者已经完成功能提交但还未补做 core 升版提交和 core tag 时，必须使用这个 skill。它负责先检测是否存在非插件改动，再在功能提交后继续调用 `./scripts/release/ak-core-release.sh` 完成 core 版本升级。只要是纯 core 改动、脚本/文档/测试等非插件改动，或插件与非插件混合改动后的 core 补发布场景，也必须使用这个 skill，不能自行猜流程或跳过补动作。
---

# Core Release Followup

这个 skill 只负责一件事：当非插件部分发生改动时，确保“先功能提交，后补一次 core 升版”的收尾流程被完整执行。

不要用这个 skill 做业务开发、代码修改方案设计或普通仓库提交。它只服务非插件改动后的 core 发布补动作。

## 何时使用

在以下任一情况，必须使用本 skill：

- 本次工作改动涉及任意非 `packages/<plugin>/` 文件
- 你准备提交非插件相关改动
- 你已经做完功能提交，但还没有补做 core 升版提交和 core tag
- 一次改动同时涉及插件与非插件内容，需要在插件发布之后继续补 core 升版

如果当前改动只涉及第一方插件目录，本 skill 应立即退出，不接管后续流程；此时由 `plugin-release-followup` 负责插件发布补动作。

## 工作流程

### 1. 提交前检测

先检查本次工作是否影响了任何非插件文件。

做法：

- 查看工作区 diff、暂存区或最近准备提交的文件范围
- 从中识别所有不在 `packages/<plugin>/` 下的路径
- 形成“存在非插件改动 / 不存在非插件改动”的明确结论

要求：

- 如果没有任何非插件改动，退出本 skill
- 只要命中至少一个非插件文件，就必须继续后续流程
- 不允许把 `packages/<plugin>/` 外的脚本、文档、测试、根配置或 core 代码忽略掉

### 2. 功能提交

先完成正常功能提交。

要求：

- 功能提交只承载业务改动
- 不要在这个提交里手工混入 core 版本 bump 或 core tag 创建
- 功能提交完成后，不能把任务视为结束

### 3. 提交后补发布

功能提交完成后，执行：

```bash
./scripts/release/ak-core-release.sh <bump-type>
```

这一步必须产生：

- 一次 core 升版提交
- 一个 core 级 tag

不要尝试跳过脚本、手写版本号或手动模拟发布步骤。core 发布入口固定就是 `./scripts/release/ak-core-release.sh`。

## 混合改动规则

如果一次功能提交同时影响第一方插件和非插件部分：

- 允许一次功能提交后产生多个连续发布提交
- 先由 `plugin-release-followup` 按 `plugin_id` 字典序补完所有插件发布
- 后补一次 core 升版
- 不允许跳过 core 补动作，也不允许把 core 补动作提前到插件发布之前

## bump 类型规则

不要随意猜测版本类型。

固定规则：

- 如果当前任务上下文已经明确版本语义，就使用对应的 `patch` / `minor` / `major`
- 如果上下文没有明确说明，默认使用 `patch`
- 不允许在没有明确依据时把默认值提升为 `minor` 或 `major`

## 禁止事项

以下行为都不允许：

- 只做功能提交，不补后续 core 升版提交
- 纯插件改动时误用本 skill 接管插件发布
- 混合改动时先补 core 升版，再补插件发布
- 不通过 `./scripts/release/ak-core-release.sh` 而改走手工发布
- 在没有依据时擅自选择 `minor` 或 `major`
- 把这个 skill 用作普通开发流程

## 完成标准

只有同时满足以下条件，才能认为非插件改动收尾完成：

- 是否存在非插件改动已经识别完成
- 功能提交已经完成
- 若存在插件改动，插件发布补动作已经先完成
- `./scripts/release/ak-core-release.sh` 已经被调用
- core 升版提交和 core tag 没有遗漏
