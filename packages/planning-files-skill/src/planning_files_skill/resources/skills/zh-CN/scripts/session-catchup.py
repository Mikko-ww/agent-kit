#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

PLANNING_FILES = ("task_plan.md", "progress.md", "findings.md")


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    if not any((root / name).exists() for name in PLANNING_FILES):
        return
    print("[planning-files] 检测到已有规划文件。")
    print("继续前请读取 task_plan.md、progress.md 和 findings.md。")


if __name__ == "__main__":
    main()

