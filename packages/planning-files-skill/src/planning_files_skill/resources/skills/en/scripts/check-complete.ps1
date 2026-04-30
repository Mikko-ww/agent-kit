$PlanFile = if ($args.Count -gt 0) { $args[0] } else { "task_plan.md" }
if (-not (Test-Path $PlanFile)) { Write-Output "[planning-files] No task_plan.md found."; exit 0 }
$Content = Get-Content $PlanFile
$Total = ($Content | Select-String "### Phase").Count
$Complete = ($Content | Select-String "\*\*Status:\*\* complete").Count
Write-Output "[planning-files] $Complete/$Total phases complete."

