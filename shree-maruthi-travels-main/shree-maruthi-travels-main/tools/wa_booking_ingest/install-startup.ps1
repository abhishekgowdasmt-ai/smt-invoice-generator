$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $python)) { $python = Join-Path $root '.venv\Scripts\python.exe' }
if (-not (Test-Path $python)) { throw 'Run install.bat first' }
$action = New-ScheduledTaskAction -Execute $python -Argument 'app.py' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'SMT-WhatsApp-Booking-Ingest' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host 'Created Windows task SMT-WhatsApp-Booking-Ingest. It starts when you log in.'
