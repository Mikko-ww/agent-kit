$PlanFile = if ($args.Count -gt 0) { $args[0] } else { "task_plan.md" }
if (-not (Test-Path $PlanFile)) { Write-Output "[planning-files] 未找到 task_plan.md。"; exit 0 }
$Content = Get-Content $PlanFile
$Total = ($Content | Select-String "### Phase").Count
$Complete = ($Content | Select-String "\*\*Status:\*\* complete").Count
Write-Output "[planning-files] $Complete/$Total 阶段完成。"

