param(
    [string]$TaskName = "SGC Dashboard Auto Sync",
    [string]$ProjectDir = $PSScriptRoot,
    [string]$PythonExe = "python",
    [string]$StartTime = "09:00"
)

$actionCmd = "cmd.exe"
$actionArgs = "/c cd /d `"$ProjectDir`" && `"$PythonExe`" auto_sync_dashboard.py --data dashboard_data.json --out-js dashboard_data.js --verbose"

$startBoundary = (Get-Date $StartTime).ToString("HH:mm")

schtasks /Create /F /TN "$TaskName" /SC DAILY /MO 3 /ST $startBoundary /TR "$actionCmd $actionArgs"
Write-Host "Scheduled task oluşturuldu: $TaskName"
