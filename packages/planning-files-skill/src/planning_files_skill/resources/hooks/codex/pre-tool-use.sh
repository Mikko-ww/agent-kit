#!/usr/bin/env bash
PLAN_FILE="task_plan.md"

if [ -f "$PLAN_FILE" ]; then
  head -30 "$PLAN_FILE" >&2
fi

echo '{"decision": "allow"}'
exit 0

