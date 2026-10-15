# dev.ps1 - starts the API (FastAPI/uvicorn) and the frontend (Vite) in dev mode (Windows).
# Before starting, it makes sure the environment is ready: creates missing .env files,
# the API venv and node_modules, and reinstalls when a dependency manifest changed.
# Hot reload on both sides (uvicorn --reload + Vite HMR). Each service opens in its own window.
#
# Do NOT run this file directly -- use the clickable _run\win.bat (double-click).
# To stop: close each window or press Ctrl+C inside it.
#
# NOTE: this file is kept ASCII-only on purpose -- Windows PowerShell 5.1 reads .ps1
# files without a BOM as ANSI, and accented characters would break parsing.

$ErrorActionPreference = 'Stop'

# Project root is two levels above this script (_run\lib\).
$root       = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$apiDir     = Join-Path $root 'backend'
$frontDir   = Join-Path $root 'frontend'
$venvPython = Join-Path $apiDir '.venv\Scripts\python.exe'

# ---------------------------------------------------------------------------
# 1) .env files (copied from .env.example when missing)
# ---------------------------------------------------------------------------
foreach ($dir in @($apiDir, $frontDir)) {
    $envFile = Join-Path $dir '.env'
    $example = Join-Path $dir '.env.example'
    if ((Test-Path $example) -and -not (Test-Path $envFile)) {
        Write-Host "[setup] missing .env in $dir - creating it from .env.example..." -ForegroundColor Yellow
        Copy-Item $example $envFile
    }
}

# ---------------------------------------------------------------------------
# 2) API venv + dependencies.
#    Creates the venv when missing and REINSTALLS when requirements.txt changed
#    (e.g. a pull from another machine added a package). Checking only that the
#    folder exists left an old venv without the new packages -> ModuleNotFoundError.
#    Marker: .venv\.requirements.stamp (touched after every install).
# ---------------------------------------------------------------------------
$reqFile  = Join-Path $apiDir 'requirements.txt'
$reqStamp = Join-Path $apiDir '.venv\.requirements.stamp'
if (-not (Test-Path $venvPython)) {
    Write-Host "[setup] API venv missing - creating it..." -ForegroundColor Yellow
    Push-Location $apiDir
    try {
        $created = $false
        # Tries, in order: py -3.13, py -3, python
        foreach ($cmd in @(@('py', '-3.13'), @('py', '-3'), @('python'))) {
            if (-not (Get-Command $cmd[0] -ErrorAction SilentlyContinue)) { continue }
            $extra = if ($cmd.Count -gt 1) { $cmd[1..($cmd.Count - 1)] } else { @() }
            & $cmd[0] @extra -m venv .venv
            if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPython)) { $created = $true; break }
        }
        if (-not $created) {
            throw "Could not create the venv. Install Python 3.13+ (https://www.python.org/downloads/)."
        }
        Write-Host "[setup] Installing API dependencies..." -ForegroundColor Yellow
        & $venvPython -m pip install --upgrade pip
        & $venvPython -m pip install -r requirements.txt
        Set-Content -Path $reqStamp -Value '' -Encoding ascii
    }
    finally { Pop-Location }
}
elseif ((Test-Path $reqFile) -and (-not (Test-Path $reqStamp) -or (Get-Item $reqFile).LastWriteTime -gt (Get-Item $reqStamp).LastWriteTime)) {
    Write-Host "[setup] requirements.txt changed - updating API dependencies..." -ForegroundColor Yellow
    & $venvPython -m pip install -r $reqFile
    Set-Content -Path $reqStamp -Value '' -Encoding ascii
}

# ---------------------------------------------------------------------------
# 3) Frontend node_modules.
#    Reinstalls when package-lock.json is newer than npm's own install record
#    (node_modules\.package-lock.json) -- e.g. a pull added a dependency.
# ---------------------------------------------------------------------------
$nodeModules   = Join-Path $frontDir 'node_modules'
$lockFile      = Join-Path $frontDir 'package-lock.json'
$installedLock = Join-Path $nodeModules '.package-lock.json'
$needNpm = (-not (Test-Path $nodeModules)) -or (-not (Test-Path $installedLock))
if (-not $needNpm -and (Test-Path $lockFile)) {
    if ((Get-Item $lockFile).LastWriteTime -gt (Get-Item $installedLock).LastWriteTime) { $needNpm = $true }
}
if ($needNpm) {
    Write-Host "[setup] frontend dependencies out of date - running npm install..." -ForegroundColor Yellow
    Push-Location $frontDir
    try { npm install }
    finally { Pop-Location }
}

# ---------------------------------------------------------------------------
# 4) Start both services, each in its own window
# ---------------------------------------------------------------------------
Write-Host "Starting API   -> http://localhost:8000  (docs at /docs)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$apiDir'; & '$venvPython' -m uvicorn app.main:app --reload --port 8000"
)

Write-Host "Starting Front -> http://localhost:5173" -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$frontDir'; npm run dev"
)

Write-Host ""
Write-Host "Two windows were opened (API and Frontend). Close them to stop." -ForegroundColor Yellow
