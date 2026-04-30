#!/usr/bin/env bash
PLAN_FILE="${1:-task_plan.md}"

if [ ! -f "$PLAN_FILE" ]; then
  echo "[planning-files] 未找到 task_plan.md。"
  exit 0
fi

TOTAL=$(grep -c "### Phase" "$PLAN_FILE" || true)
COMPLETE=$(grep -cF "**Status:** complete" "$PLAN_FILE" || true)

if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
  echo "[planning-files] 所有阶段已完成 ($COMPLETE/$TOTAL)。"
else
  echo "[planning-files] 任务仍在进行 ($COMPLETE/$TOTAL 阶段完成)。"
fi

exit 0

