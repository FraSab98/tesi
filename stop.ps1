<#
.SYNOPSIS
    Ferma tutti i servizi del progetto Cognitive Assessment Platform.
.DESCRIPTION
    - Ferma i container Docker
    - Chiude i processi uvicorn (backend) e node (frontend)
.NOTES
    Lanciare da PowerShell nella cartella radice del progetto.
#>

function Write-Step { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [!]  $msg" -ForegroundColor Yellow }

$ROOT = $PSScriptRoot
if (-Not $ROOT) { $ROOT = Get-Location }
Set-Location $ROOT

Write-Host "############################################################" -ForegroundColor Magenta
Write-Host "#  STOP — Cognitive Assessment Platform                    #" -ForegroundColor Magenta
Write-Host "############################################################" -ForegroundColor Magenta

# ============ 1. CONTAINER DOCKER ============
Write-Step "1/3 Arresto container Docker"
docker compose down
Write-Ok "Container Docker fermati"

# ============ 2. BACKEND (uvicorn) ============
Write-Step "2/3 Arresto backend (uvicorn)"
$uvicornProcs = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like "*uvicorn*app.main*"
}
if ($uvicornProcs) {
    foreach ($proc in $uvicornProcs) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Ok "Backend fermato"
} else {
    Write-Warn "Nessun processo backend trovato (forse gia' chiuso)"
}

# ============ 3. FRONTEND (node/vite) ============
Write-Step "3/3 Arresto frontend (vite)"
$viteProcs = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like "*vite*" -or $_.CommandLine -like "*npm*dev*"
}
if ($viteProcs) {
    foreach ($proc in $viteProcs) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Ok "Frontend fermato"
} else {
    Write-Warn "Nessun processo frontend trovato (forse gia' chiuso)"
}

Write-Host "`n############################################################" -ForegroundColor Green
Write-Host "#  TUTTO FERMATO                                           #" -ForegroundColor Green
Write-Host "############################################################" -ForegroundColor Green
Write-Host "`nNota: le finestre PowerShell del backend/frontend potrebbero" -ForegroundColor Gray
Write-Host "essere ancora aperte. Puoi chiuderle manualmente." -ForegroundColor Gray
Write-Host ""
