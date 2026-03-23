# skills-link 插件说明

本目录继承上级 [../AGENTS.md](../AGENTS.md) 与根目录 [../../AGENTS.md](../../AGENTS.md) 的规则，本文只补充 `skills-link` 自身的业务约束。

## 1. 插件目标

`skills-link` 负责把本地 skills 源目录中的技能目录，以目录粒度软链接到一个或多个目标目录，方便在多个目标环境中统一使用这些 skills。

## 2. 命令

当前插件对外提供以下命令：

- `agent-kit skills-link init`
- `agent-kit skills-link list`
- `agent-kit skills-link link`
- `agent-kit skills-link unlink`
- `agent-kit skills-link status`
- `agent-kit skills-link target list`
- `agent-kit skills-link target add`
- `agent-kit skills-link target update`
- `agent-kit skills-link target remove`

对应实现入口：

- [src/skills_link/plugin_cli.py](src/skills_link/plugin_cli.py)
- [src/skills_link/messages.py](src/skills_link/messages.py)
- [src/skills_link/locale.py](src/skills_link/locale.py)

## 3. 配置

配置文件位置：

- `~/.config/agent-kit/plugins/skills-link/config.jsonc`

当前配置核心字段：

- `plugin_id`
- `config_version`
- `source_dir`
- `targets`

其中 `targets` 为 target 注册表，元素至少包含：

- `name`
- `path`

配置读写实现：

- [src/skills_link/config.py](src/skills_link/config.py)

## 4. 业务规则

- 只识别 `source_dir` 下一层直接子目录中包含 `SKILL.md` 的目录。
- 只按目录粒度处理 skill，不做文件级选择。
- `link` / `unlink` / `list` / `status` 默认作用全部 target，可用 `--target <name>` 缩小范围。
- `link` 只创建目录软链接，不复制文件。
- 若目标位置已存在同名文件、目录或不受管链接，一律视为冲突，不覆盖。
- `unlink` 只删除指向当前 `source_dir/<skill>` 的受管软链接，不删除真实目录或外部链接。
- `target add` 只登记 target，不自动执行 skill 链接。
- `target update` 改名只更新配置；改 path 时，若旧 path 下仍存在受管链接，则必须先 `unlink --target <name>`。
- `target remove` 只删除配置项，不删除真实目录；若仍存在受管链接，则必须先 `unlink --target <name>`。
- 当前仅支持 macOS / Linux，不处理 Windows。

核心业务实现：

- [src/skills_link/logic.py](src/skills_link/logic.py)

## 5. 修改本插件时重点验证

- `init` 是否正确写入新的多 target `config.jsonc`
- `target add/list/update/remove` 是否正确维护 target 注册表
- `list` 是否按 skill 视角展示各 target 的 `linked`、`not_linked`、`broken_link`、`conflict`
- `link` 是否按 `(skill, target)` 粒度创建受管软链接并正确报告冲突
- `unlink` 是否按 `(skill, target)` 粒度只删除受管软链接
- `status` 是否按 target 维度正确汇总 source/target 可用性和状态计数
- `--target` 过滤是否正确处理单个、多值和未知 target name
- 中英文下的 `--help`、初始化提示、warning/error、状态输出是否保持一致

相关测试：

- [tests/test_skill_link_cli.py](tests/test_skill_link_cli.py)
- [tests/test_skill_link_logic.py](tests/test_skill_link_logic.py)
