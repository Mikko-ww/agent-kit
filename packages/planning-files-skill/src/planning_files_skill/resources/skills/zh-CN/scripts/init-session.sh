#!/usr/bin/env bash
set -e

DATE=$(date +%Y-%m-%d)

if [ ! -f task_plan.md ]; then
  cp "$(dirname "$0")/../templates/task_plan.md" task_plan.md 2>/dev/null || echo "# 任务计划：[简要描述]" > task_plan.md
  echo "已创建 task_plan.md"
fi

if [ ! -f findings.md ]; then
  cp "$(dirname "$0")/../templates/findings.md" findings.md 2>/dev/null || echo "# 发现与决策" > findings.md
  echo "已创建 findings.md"
fi

if [ ! -f progress.md ]; then
  cp "$(dirname "$0")/../templates/progress.md" progress.md 2>/dev/null || echo "# 进度日志" > progress.md
  printf '\n开始时间：%s\n' "$DATE" >> progress.md
  echo "已创建 progress.md"
fi

echo "规划文件已就绪。"

