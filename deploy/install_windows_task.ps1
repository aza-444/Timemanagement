# PowerShell Script to install Telegram Bot as Windows Scheduled Task (Runs on System Startup)
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$BatPath = Join-Path $ProjectDir "deploy\start_windows.bat"
$TaskName = "TelegramExpenseTrackerBot"

Write-Host "=== Setting up Windows Task Scheduler for Telegram Bot ===" -ForegroundColor Green
Write-Host "Project Directory: $ProjectDir"
Write-Host "Batch Path: $BatPath"

# Check if Task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Removing existing scheduled task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Define Actions and Triggers
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $ProjectDir
$triggerAtStartup = New-ScheduledTaskTrigger -AtStartup
$triggerOnLogon = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Register Scheduled Task
Register-ScheduledTask -TaskName $TaskName `
    -Action $action `
    -Trigger @($triggerAtStartup, $triggerOnLogon) `
    -Settings $settings `
    -Description "Runs Telegram Expense Tracker Bot automatically on server boot." `
    -User "SYSTEM" `
    -RunLevel Highest

Write-Host "SUCCESS: Task '$TaskName' installed successfully!" -ForegroundColor Green
Write-Host "The bot will now start automatically whenever Windows boots up." -ForegroundColor Green
