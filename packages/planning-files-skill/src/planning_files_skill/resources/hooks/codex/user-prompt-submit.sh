#!/usr/bin/env bash
if [ -f task_plan.md ]; then
  echo "[planning-files] ACTIVE PLAN - current state:"
  head -50 task_plan.md
  echo ""
  echo "=== recent progress ==="
  tail -20 progress.md 2>/dev/null
  echo ""
  echo "[planning-files] Read findings.md for research context. Continue from the current phase."
fi
exit 0

