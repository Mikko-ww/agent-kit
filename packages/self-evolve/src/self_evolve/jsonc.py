from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def loads_jsonc(content: str) -> Any:
    return json.loads(_strip_json_comments(content))


def load_jsonc(path: Path) -> Any:
    return loads_jsonc(path.read_text(encoding="utf-8"))


def dump_jsonc(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_jsonc(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_jsonc(data), encoding="utf-8")
    return path


def merge_flat_jsonc(raw: str, values: dict) -> str:
    """更新平铺 JSONC 中的字段值，保留注释和格式。

    仅适用于顶层无嵌套、值为 JSON 原始类型（string / number / bool / null）的对象。
    逐行处理，跳过纯注释行，对匹配到的 "key": value 只替换 value 部分。
    """
    import re

    lines = raw.split("\n")
    pending = dict(values)
    result: list[str] = []

    _VALUE = r'(?:"(?:[^"\\]|\\.)*"|[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|true|false|null)'

    for line in lines:
        if not pending:
            result.append(line)
            continue

        stripped = line.lstrip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            result.append(line)
            continue

        matched = False
        for key in list(pending):
            pattern = r'("' + re.escape(key) + r'"\s*:\s*)' + _VALUE
            m = re.search(pattern, line)
            if m:
                new_val = json.dumps(pending[key], ensure_ascii=False)
                prefix = line[: m.start()]
                key_colon = m.group(1)
                tail = line[m.end() :]
                tail = _fix_displaced_comma(tail)
                result.append(prefix + key_colon + new_val + tail)
                del pending[key]
                matched = True
                break

        if not matched:
            result.append(line)

    return "\n".join(result)


def _fix_displaced_comma(tail: str) -> str:
    """如果逗号被位移到行内注释中，将其移回注释前。"""
    comment_idx = -1
    for i in range(len(tail)):
        if tail[i] == "/" and i + 1 < len(tail) and tail[i + 1] == "/":
            comment_idx = i
            break
    if comment_idx < 0:
        return tail
    pre_comment = tail[:comment_idx]
    comment = tail[comment_idx:]
    if "," in pre_comment:
        return tail
    stripped_comment = comment.rstrip()
    if stripped_comment.endswith(","):
        fixed_comment = stripped_comment[:-1]
        trailing = comment[len(stripped_comment) :]
        return "," + pre_comment + fixed_comment + trailing
    return tail


def _strip_json_comments(content: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False
    index = 0
    length = len(content)

    while index < length:
        char = content[index]
        next_char = content[index + 1] if index + 1 < length else ""

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            index += 2
            while index < length and content[index] not in "\r\n":
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and not (
                content[index] == "*" and content[index + 1] == "/"
            ):
                index += 1
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)
