# skills-link

`skills-link` 是 `agent-kit` 的第一方插件，用于把本地 `source_dir` 中的 skill 目录，以目录级软链接方式同步到一个或多个 target 目录。

## 核心能力

- 单个 `source_dir`，多个 target
- 按目录粒度识别 skill，要求目录下存在 `SKILL.md`
- `link` / `unlink` / `list` / `status` 默认作用全部 target
- 支持用 `--target <name>` 精确限制命令作用范围
- 提供 `target add/list/update/remove` 管理 target 注册表

## 配置文件

插件配置保存在：

```text
~/.config/agent-kit/plugins/skills-link/config.jsonc
```

配置结构：

```json
{
  "plugin_id": "skills-link",
  "config_version": 2,
  "source_dir": "/path/to/skills",
  "targets": [
    {
      "name": "codex",
      "path": "/path/to/codex/skills"
    },
    {
      "name": "claude",
      "path": "/path/to/claude/skills"
    }
  ]
}
```

## 命令

初始化与技能同步命令：

```bash
agent-kit skills-link init
agent-kit skills-link list
agent-kit skills-link list --target codex
agent-kit skills-link link
agent-kit skills-link link --target codex --target claude
agent-kit skills-link unlink --target codex
agent-kit skills-link status
```

target 管理命令：

```bash
agent-kit skills-link target list
agent-kit skills-link target add --name codex --path /path/to/codex/skills
agent-kit skills-link target update --name codex --new-name codex-dev
agent-kit skills-link target update --name codex --path /new/path/to/codex/skills
agent-kit skills-link target remove --name codex
```

## 行为约束

- 只识别 `source_dir` 下一层直接子目录中包含 `SKILL.md` 的目录
- 只创建目录软链接，不复制文件
- 若目标位置已存在同名文件、目录或不受管链接，一律视为冲突，不覆盖
- `unlink` 只删除指向当前 `source_dir/<skill>` 的受管软链接
- `target add` 只登记 target，不自动执行链接
- `target update --path` 和 `target remove` 在存在受管链接时会拒绝执行，并提示先运行 `unlink --target <name>`
- 当前仅支持 macOS / Linux
