# planning-files-skill

`planning-files-skill` 是 `agent-kit` 的第一方插件，用于把 `planning-files` skill 导入到 Codex、Cursor、OpenCode 或通用 Agent Skills 目录。

## 核心能力

- 支持 `codex`、`cursor`、`opencode`、`generic` 四类平台目标。
- 支持 `en` 和 `zh-CN` 两种 skill 内容语言。
- Codex 与 Cursor 导入时会同步 hooks 脚本并安全合并 hooks 配置。
- OpenCode 与 generic 目标只导入 skill 文件、模板、脚本和参考资料。
- 实际被 Agent 加载的 skill 名称固定为 `planning-files`。

## 命令

```bash
agent-kit planning-files-skill import --platform codex --language zh-CN --scope project
agent-kit planning-files-skill import --platform all --language en --scope global
agent-kit planning-files-skill status --platform codex --scope project
```

短名：

```bash
agent-kit pfs status --platform generic
```

## 目标路径

- Codex：`.codex/skills/planning-files/` 或 `~/.codex/skills/planning-files/`
- Cursor：`.cursor/skills/planning-files/` 或 `~/.cursor/skills/planning-files/`
- OpenCode：`.opencode/skills/planning-files/` 或 `~/.config/opencode/skills/planning-files/`
- Generic：`.agents/skills/planning-files/` 或 `~/.agents/skills/planning-files/`

Codex hooks 需要用户在 `~/.codex/config.toml` 的 `[features]` 中启用：

```toml
codex_hooks = true
```

## 行为约束

- 插件命令名是 `planning-files-skill`，skill 名称是 `planning-files`。
- 目标 skill 目录已有非托管内容时，默认拒绝覆盖；可使用 `--force` 覆盖插件管理的资源文件。
- `--dry-run` 只预览变更，不写入文件。
- hooks 配置会保留用户已有条目，只新增或更新本插件管理的条目。

