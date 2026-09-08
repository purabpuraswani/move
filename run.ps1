<#
.SYNOPSIS
    Single-command launcher for MoveWell AI (Backend + Frontend).

.DESCRIPTION
    Starts the FastAPI backend (with dual 8000/8100 compatibility) and
    the Vite frontend dev server (port 5173).
#>

[CmdletBinding()]
param()

$Root = $PSScriptRoot
$BackendDir = Join-Path $Root 'backend'
$VenvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "        Launching MoveWell AI Application         " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Start Backend on Port 8000
$p8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if (-not $p8000) {
    Write-Host "Starting Backend API on http://127.0.0.1:8000..." -ForegroundColor Green
    Start-Process -FilePath $VenvPython `
        -ArgumentList '-m', 'uvicorn', 'main:app', '--reload', '--port', '8000' `
        -WorkingDirectory $BackendDir
} else {
    Write-Host "Backend API is already running on port 8000." -ForegroundColor Yellow
}

# 2. Start Backend on Port 8100 (dual-port bridge for legacy configs)
$p8100 = Get-NetTCPConnection -LocalPort 8100 -ErrorAction SilentlyContinue
if (-not $p8100) {
    Write-Host "Starting Backend API compatibility bridge on http://127.0.0.1:8100..." -ForegroundColor Green
    Start-Process -FilePath $VenvPython `
        -ArgumentList '-m', 'uvicorn', 'main:app', '--reload', '--port', '8100' `
        -WorkingDirectory $BackendDir
} else {
    Write-Host "Backend API compatibility bridge is already active on port 8100." -ForegroundColor Yellow
}

# 3. Start Frontend Dev Server on Port 5173
$p5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if (-not $p5173) {
    Write-Host "Starting Vite frontend on http://localhost:5173..." -ForegroundColor Green
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', 'npm.cmd run dev' `
        -WorkingDirectory $Root
} else {
    Write-Host "Frontend is already running on http://localhost:5173." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "All services active:" -ForegroundColor Cyan
Write-Host "  - Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  - Backend API: http://127.0.0.1:8000 and http://127.0.0.1:8100" -ForegroundColor White
Write-Host "  - API Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
