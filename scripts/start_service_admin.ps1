# Start the Game Orchestrator service elevated (run as Administrator).
#
# Why not a scheduled task: on this machine, processes started by Task Scheduler
# run at *Low* integrity level, so they cannot write game folders (M7A config,
# BetterGI logs). Starting from this elevated window directly yields High IL.

$ErrorActionPreference = 'Stop'

$python  = 'D:\DSH_WorkSpace\Game_play\server\.venv\Scripts\python.exe'
$script  = 'D:\DSH_WorkSpace\Game_play\server\run.py'
$workdir = 'D:\DSH_WorkSpace\Game_play\server'
$port    = 8765

Write-Host "=== Game Orchestrator - Start Elevated ===" -ForegroundColor Cyan

$who = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal($who)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: not running as Administrator." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] running as Administrator ($($who.Name))" -ForegroundColor Green

# stop old listeners / old scheduled-task instance
$ErrorActionPreference = 'Continue'
& schtasks /end /tn GameOrchestrator 2>&1 | Out-Null
$conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    foreach ($c in $conn) {
        Write-Host "  stopping old process PID=$($c.OwningProcess)"
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}
$ErrorActionPreference = 'Stop'
Write-Host "[OK] port $port is free" -ForegroundColor Green

# start directly (inherits this window's integrity level)
$p = Start-Process -FilePath $python -ArgumentList "`"$script`"" -WorkingDirectory $workdir `
     -WindowStyle Minimized -PassThru
Write-Host "[OK] service process started, PID=$($p.Id)" -ForegroundColor Green

$ok = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 2
        if ($r.ok) { $ok = $true; break }
    } catch { }
}
if (-not $ok) {
    Write-Host "ERROR: service did not answer /api/health." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] service healthy (version $($r.version))" -ForegroundColor Green

# verify integrity level through the service itself
$authFile = Join-Path $workdir 'data\auth.json'
if (Test-Path $authFile) {
    $token = (Get-Content $authFile -Raw | ConvertFrom-Json).tokens[0].token
    try {
        $info = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/debug/token" `
                -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 10
        $label = ($info.whoami_all -split "`n" | Select-String 'Mandatory').Line
        Write-Host "     integrity = $($label.Trim())" -ForegroundColor Cyan

        if ($label -match 'Low') {
            Write-Host ""
            Write-Host "*** WARNING: still Low integrity. ***" -ForegroundColor Red
        } else {
            # quick write test into M7A folder
            try {
                $w = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/debug/write-test" -Method Post `
                     -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' `
                     -Body '{"dir":"F:/星穹铁道/March7thAssistant_full"}' -TimeoutSec 10
                if ($w.writable) {
                    Write-Host "[OK] can write game folder (M7A) - all good!" -ForegroundColor Green
                } else {
                    Write-Host "[WARN] cannot write M7A folder: $($w.error)" -ForegroundColor Yellow
                }
            } catch { }
        }
    } catch {
        Write-Host "     (could not query integrity: $_)" -ForegroundColor Yellow
    }
} else {
    Write-Host "     (auth.json not found, skip integrity check)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Service is running. Keep this window open? No - it already detached." -ForegroundColor Gray
Write-Host "Tell the assistant 'started' and the integrity line above." -ForegroundColor Cyan
