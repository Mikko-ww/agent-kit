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
