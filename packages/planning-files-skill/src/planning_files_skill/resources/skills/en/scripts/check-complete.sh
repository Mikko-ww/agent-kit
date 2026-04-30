#!/usr/bin/env bash
PLAN_FILE="${1:-task_plan.md}"

if [ ! -f "$PLAN_FILE" ]; then
  echo "[planning-files] No task_plan.md found."
  exit 0
fi

TOTAL=$(grep -c "### Phase" "$PLAN_FILE" || true)
COMPLETE=$(grep -cF "**Status:** complete" "$PLAN_FILE" || true)
IN_PROGRESS=$(grep -cF "**Status:** in_progress" "$PLAN_FILE" || true)
PENDING=$(grep -cF "**Status:** pending" "$PLAN_FILE" || true)

if [ "$COMPLETE" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ] && [ "$PENDING" -eq 0 ]; then
  COMPLETE=$(grep -c "\[complete\]" "$PLAN_FILE" || true)
  IN_PROGRESS=$(grep -c "\[in_progress\]" "$PLAN_FILE" || true)
  PENDING=$(grep -c "\[pending\]" "$PLAN_FILE" || true)
fi

if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
  echo "[planning-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL)."
else
  echo "[planning-files] Task in progress ($COMPLETE/$TOTAL phases complete)."
fi

exit 0

