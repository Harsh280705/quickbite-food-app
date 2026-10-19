<#
.SYNOPSIS
    Controlled start/stop/status control for the QuickBite API (local venv).

.DESCRIPTION
    This replaces ad-hoc Start-Process invocations:
      * refuses to start a duplicate instance (port + PID file checks),
      * only ever touches processes whose command line points at THIS
        workspace (never unrelated python.exe processes),
      * writes logs and a PID file inside the workspace,
      * waits a bounded time for /health/live and prints the result.

.PARAMETER Action
    start | stop | status

.EXAMPLE
    powershell -File scripts\api.ps1 -Action start
    powershell -File scripts\api.ps1 -Action status
    powershell -File scripts\api.ps1 -Action stop
#>
[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action = 'status',
    [int]$Port = 8000,
    [ValidateSet('127.0.0.1', '0.0.0.0')]
    [string]$ListenHost = '127.0.0.1',
    [int]$HealthTimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $WorkspaceRoot 'backend'
$LogDir = Join-Path $WorkspaceRoot 'logs'
$PythonExe = Join-Path $WorkspaceRoot '.venv\Scripts\python.exe'
$OutLog = Join-Path $LogDir 'api.out.log'
$ErrLog = Join-Path $LogDir 'api.err.log'
$PidFile = Join-Path $LogDir 'api.pid'

# Everything must stay inside the workspace.
foreach ($path in @($BackendDir, $LogDir, $PythonExe)) {
    if (-not $path.StartsWith($WorkspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside the workspace: $path"
    }
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Project virtualenv missing: $PythonExe"
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Get-QuickBiteApiProcesses {
    <# Only processes launched from this workspace with the API command line. #>
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -like '*uvicorn*app.main:app*' -and
            $_.CommandLine -like "*$WorkspaceRoot*"
        }
}

function Get-ListeningPid([int]$PortNumber) {
    $conn = Get-NetTCPConnection -LocalPort $PortNumber -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) { return $conn.OwningProcess }
    return $null
}

switch ($Action) {
    'status' {
        $procs = Get-QuickBiteApiProcesses
        if ($procs) {
            $procs | Select-Object ProcessId, ParentProcessId, Name, CreationDate | Format-Table -AutoSize | Out-String | Write-Host
        }
        else {
            Write-Host "no QuickBite API processes found"
        }
        $listener = Get-ListeningPid -PortNumber $Port
        Write-Host ("port {0} listener pid: {1}" -f $Port, $(if ($listener) { $listener } else { '<none>' }))
        try {
            $live = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health/live" -TimeoutSec 3 -UseBasicParsing
            Write-Host "GET /health/live -> $($live.StatusCode) $($live.Content)"
        }
        catch {
            Write-Host "GET /health/live -> FAILED ($($_.Exception.Message))"
        }
    }

    'start' {
        $existing = Get-QuickBiteApiProcesses
        $listener = Get-ListeningPid -PortNumber $Port
        if ($existing -or $listener) {
            Write-Host "A QuickBite API instance is already running (processes: $($existing.ProcessId -join ',') listener: $listener)."
            Write-Host "Use -Action status instead of starting a duplicate."
            $Action = 'status'
        }
        else {
            $proc = Start-Process -FilePath $PythonExe `
                -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', $ListenHost, '--port', "$Port" `
                -WorkingDirectory $BackendDir `
                -RedirectStandardOutput $OutLog `
                -RedirectStandardError $ErrLog `
                -PassThru
            Set-Content -LiteralPath $PidFile -Value $proc.Id -Encoding ascii
            Write-Host "started launcher pid $($proc.Id); logs: $OutLog / $ErrLog"

            $deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
            $ok = $false
            while ((Get-Date) -lt $deadline) {
                Start-Sleep -Milliseconds 500
                try {
                    $live = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health/live" -TimeoutSec 2 -UseBasicParsing
                    if ($live.StatusCode -eq 200) { $ok = $true; break }
                }
                catch { }
            }
            if ($ok) {
                Write-Host "health OK after bounded wait (<= $HealthTimeoutSeconds s)"
                $procs = Get-QuickBiteApiProcesses
                $procs | Select-Object ProcessId, ParentProcessId, Name, CreationDate | Format-Table -AutoSize | Out-String | Write-Host
                Write-Host "--- startup log line ---"
                Select-String -LiteralPath $OutLog -Pattern 'api_starting' | Select-Object -Last 1 | ForEach-Object { $_.Line } | Write-Host
            }
            else {
                Write-Host "API did not become healthy within $HealthTimeoutSeconds s. Inspect $ErrLog"
                Get-Content -LiteralPath $ErrLog -Tail 20 | Write-Host
                exit 1
            }
        }
    }

    'stop' {
        $procs = Get-QuickBiteApiProcesses
        if (-not $procs) {
            Write-Host "no QuickBite API processes to stop"
            if (Test-Path -LiteralPath $PidFile) { Remove-Item -LiteralPath $PidFile -Force }
            exit 0
        }
        # Stop children first, then launchers.
        $ordered = $procs | Sort-Object -Property @{ Expression = { $_.ParentProcessId -in $procs.ProcessId } }
        foreach ($p in $ordered) {
            if ($p.CommandLine -like "*$WorkspaceRoot*") {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
                Write-Host "stopped pid $($p.ProcessId)"
            }
        }
        Start-Sleep -Milliseconds 700
        if (Test-Path -LiteralPath $PidFile) { Remove-Item -LiteralPath $PidFile -Force }
        $left = Get-QuickBiteApiProcesses
        Write-Host ("remaining QuickBite API processes: {0}" -f $(if ($left) { ($left.ProcessId -join ',') } else { '<none>' }))
    }
}
