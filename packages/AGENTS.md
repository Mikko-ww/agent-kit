# 插件目录说明

本目录继承根目录 [../AGENTS.md](../AGENTS.md) 的全局规则，本文只补充所有插件共享约束。

## 1. 关键提醒

- 新插件默认不要再使用 `agent-kit-` 前缀。
- 插件分发名、目录名和 `plugin_id` 应尽量保持短而一致。
- 每个插件都必须有自己的目录级 `AGENTS.md`，不要把插件私有规则继续堆到根目录。
- 所有插件的用户可见文本都必须接入多语言消息层，不能继续直接写死在 CLI 逻辑里。

## 2. 命名规范

- 分发包名使用短名称，例如 `skills-link`
- 目录名与分发包名保持一致，例如 `packages/skills-link`
- Python 模块名使用下划线形式，例如 `skills_link`
- `plugin_id` 与对外命令名保持一致，例如 `skills-link`

## 3. 插件协议

每个插件必须满足以下要求：

- 在自己的环境中暴露统一入口 `agent-kit-plugin`
- 支持 `agent-kit-plugin --plugin-metadata`
- 元数据至少返回：
  - `plugin_id`
  - `installed_version`
  - `api_version`
  - `config_version`
- 使用自己的 `config.jsonc` 保存业务配置
- 被 core 启动时必须遵从 core 透传的 `AGENT_KIT_LANG`
- 直接运行 `agent-kit-plugin` 时，仍需按 `env > global config > system locale > en` 回退

## 4. 新增插件 Checklist

新增一个官方插件时，至少完成这些事项：

1. 在 `packages/` 下新增独立包目录。
2. 定义分发包名、目录名、Python 模块名和 `plugin_id`。
3. 提供 `agent-kit-plugin` script。
4. 实现 `--plugin-metadata`。
5. 定义自己的 `config.jsonc` 结构与 `config_version`。
6. 在两个官方注册表文件中增加条目：
   - [../registry/official.json](../registry/official.json)
   - [../src/agent_kit/official_registry.json](../src/agent_kit/official_registry.json)
7. 新增该插件根目录的 `AGENTS.md`。
8. 增加 core 生命周期测试和插件自己的 CLI/逻辑测试。

## 5. 测试要求

- 插件自己的行为测试放在 `packages/<plugin>/tests/`
- 改插件协议时，同时检查 core 相关测试是否需要调整
- 改插件 CLI 文案时，同时检查 `--help`、交互提示、warning/error、状态输出是否覆盖到中英文测试
- 声称完成前至少执行一次 `uv run pytest`
