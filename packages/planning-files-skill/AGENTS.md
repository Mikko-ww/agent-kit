# planning-files-skill 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `planning-files-skill` 自身约束。

## 1. 插件定位

`planning-files-skill` 负责把包内自带的 `planning-files` skill 资源导入到 Codex、Cursor、OpenCode 或通用 Agent Skills 目录。

## 2. 命名约束

- 插件分发包名、目录名、`plugin_id` 和命令名固定为 `planning-files-skill`。
- Python 模块名固定为 `planning_files_skill`。
- 导入后的 skill 目录名和 `SKILL.md` frontmatter `name` 固定为 `planning-files`。
- 不要把源项目名 `planning-with-files` 作为 agent-kit 的对外插件命令名。

## 3. 支持范围

当前只支持：

- 平台：`codex`、`cursor`、`opencode`、`generic`
- 语言：`en`、`zh-CN`
- 范围：`project`、`global`

不要在本插件中恢复 Claude plugin、Gemini、Kiro、Hermes、analytics 模板或额外多语言，除非用户明确确认扩大范围。

## 4. 导入规则

- Codex 与 Cursor 导入时同步 skill 资源、hooks 脚本，并安全合并 hooks 配置。
- OpenCode 与 generic 只同步 skill 资源。
- hooks 配置必须保留用户已有条目，不允许直接覆盖整个 `hooks.json`。
- 目标 skill 目录没有本插件 manifest 且已有内容时，默认拒绝覆盖；只有 `--force` 可以覆盖插件资源清单中的文件。
- Codex 只提示用户启用 `codex_hooks = true`，不得自动修改用户的 `~/.codex/config.toml`。

## 5. 测试关注点

- `import`、`status`、`--dry-run`、`--force`
- project/global 路径解析
- manifest 幂等更新
- hooks 合并与非法 JSON 报错
- 中英文 CLI 帮助与输出

