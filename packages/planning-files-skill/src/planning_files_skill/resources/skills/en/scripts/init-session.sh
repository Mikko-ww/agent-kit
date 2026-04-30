#!/usr/bin/env bash
set -e

DATE=$(date +%Y-%m-%d)

if [ ! -f task_plan.md ]; then
  cp "$(dirname "$0")/../templates/task_plan.md" task_plan.md 2>/dev/null || cat > task_plan.md <<'EOF'
# Task Plan: [Brief Description]

## Goal
[One sentence describing the end state]

## Current Phase
Phase 1
EOF
  echo "Created task_plan.md"
fi

if [ ! -f findings.md ]; then
  cp "$(dirname "$0")/../templates/findings.md" findings.md 2>/dev/null || echo "# Findings & Decisions" > findings.md
  echo "Created findings.md"
fi

if [ ! -f progress.md ]; then
  cp "$(dirname "$0")/../templates/progress.md" progress.md 2>/dev/null || echo "# Progress Log" > progress.md
  printf '\nStarted: %s\n' "$DATE" >> progress.md
  echo "Created progress.md"
fi

echo "Planning files ready."

