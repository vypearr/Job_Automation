param(
    [string]$TaskPrefix = "JobAgent Handshake",
    [int]$SubmitLimit = 25,
    [string[]]$Times = @("09:00", "17:00")
)

$ErrorActionPreference = "Stop"

$repoDir = Split-Path -Parent $PSScriptRoot
$runnerPath = Join-Path $PSScriptRoot "run_unattended_handshake_cycle.cmd"

if (-not (Test-Path $runnerPath)) {
    throw "Runner script not found: $runnerPath"
}

$taskNames = @(
    "$TaskPrefix Morning",
    "$TaskPrefix Evening"
)

$timePairs = @()
for ($i = 0; $i -lt [Math]::Min($taskNames.Count, $Times.Count); $i++) {
    $timePairs += [PSCustomObject]@{
        TaskName = $taskNames[$i]
        Time = $Times[$i]
    }
}

foreach ($pair in $timePairs) {
    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$runnerPath`" $SubmitLimit"

    $trigger = New-ScheduledTaskTrigger -Daily -At $pair.Time

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew

    Register-ScheduledTask `
        -TaskName $pair.TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Runs the unattended Handshake intake plus local submit cycle for the job agent." `
        -User $env:USERNAME `
        -Force | Out-Null

    Write-Output "Registered task: $($pair.TaskName) at $($pair.Time)"
}

Write-Output "Runner path: $runnerPath"
Write-Output "Repo path: $repoDir"
Write-Output "Logs: $(Join-Path $repoDir 'data\logs')"
