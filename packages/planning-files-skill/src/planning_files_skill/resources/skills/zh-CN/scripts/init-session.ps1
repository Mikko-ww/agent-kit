$Date = Get-Date -Format "yyyy-MM-dd"
if (-not (Test-Path "task_plan.md")) { "# 任务计划：[简要描述]`n" | Out-File -Encoding utf8 "task_plan.md" }
if (-not (Test-Path "findings.md")) { "# 发现与决策`n" | Out-File -Encoding utf8 "findings.md" }
if (-not (Test-Path "progress.md")) { "# 进度日志`n`n开始时间：$Date`n" | Out-File -Encoding utf8 "progress.md" }
Write-Output "规划文件已就绪。"

