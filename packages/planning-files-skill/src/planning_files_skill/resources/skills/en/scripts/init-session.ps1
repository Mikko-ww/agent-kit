$Date = Get-Date -Format "yyyy-MM-dd"
if (-not (Test-Path "task_plan.md")) { "# Task Plan: [Brief Description]`n" | Out-File -Encoding utf8 "task_plan.md" }
if (-not (Test-Path "findings.md")) { "# Findings & Decisions`n" | Out-File -Encoding utf8 "findings.md" }
if (-not (Test-Path "progress.md")) { "# Progress Log`n`nStarted: $Date`n" | Out-File -Encoding utf8 "progress.md" }
Write-Output "Planning files ready."

