from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_jsonc(path: Path) -> Any:
    return loads_jsonc(path.read_text(encoding="utf-8"))


def loads_jsonc(raw: str) -> Any:
    return json.loads(_strip_jsonc_comments(raw))


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _strip_jsonc_comments(raw: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    lines: list[str] = []
    for line in without_block.splitlines():
        lines.append(_strip_line_comment(line))
    return "\n".join(lines)


def _strip_line_comment(line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string and char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            return line[:index]
    return line

