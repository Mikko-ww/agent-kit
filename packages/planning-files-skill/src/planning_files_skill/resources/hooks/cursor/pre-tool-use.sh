#!/usr/bin/env bash
if [ -f task_plan.md ]; then
  head -30 task_plan.md >&2
fi
echo '{"decision": "allow"}'
exit 0

