<#
.SYNOPSIS
    Avvia l'intero progetto Cognitive Assessment Platform.
.DESCRIPTION
    - Avvia i container Docker (PostgreSQL, MinIO, Redis)
    - Avvia il backend FastAPI in una nuova finestra
    - Avvia il frontend React in una nuova finestra
    - Apre il browser sulle pagine giuste
.NOTES
    Eseguire setup.ps1 PRIMA di questo script (una sola volta).
    Lanciare da PowerShell nella cartella radice del progetto.
    Se ricevi un errore sui permessi, lancia prima:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "  [X]  $msg" -ForegroundColor Red }

# Cartella radice = cartella in cui si trova questo script
$ROOT = $PSScriptRoot
if (-Not $ROOT) { $ROOT = Get-Location }
Set-Location $ROOT

Write-Host "############################################################" -ForegroundColor Magenta
Write-Host "#  AVVIO — Cognitive Assessment Platform                   #" -ForegroundColor Magenta
Write-Host "############################################################" -ForegroundColor Magenta

# ============ CONTROLLI PRELIMINARI ============
Write-Step "Controlli preliminari"

# Docker attivo?
docker ps 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker non e' attivo. Apri Docker Desktop e riprova."
    exit 1
}
Write-Ok "Docker attivo"

# .env esiste?
if (-Not (Test-Path ".env")) {
    Write-Err "File .env mancante. Lancia prima setup.ps1"
    exit 1
}

# La chiave API e' configurata?
$envContent = Get-Content ".env" -Raw
if ($envContent -match "ANTHROPIC_API_KEY=sk-ant-your-key-here" -or $envContent -notmatch "ANTHROPIC_API_KEY=sk-ant-") {
    Write-Warn "ANTHROPIC_API_KEY non sembra configurata nel file .env"
    Write-Warn "La generazione dei test via LLM non funzionera' finche' non la imposti."
    $continue = Read-Host "  Vuoi continuare comunque? (s/n)"
    if ($continue -ne "s") { exit 0 }
}

# venv esiste?
if (-Not (Test-Path "backend\.venv")) {
    Write-Err "Virtual environment mancante. Lancia prima setup.ps1"
    exit 1
}
Write-Ok "Configurazione OK"

# ============ 1. DATABASE (DOCKER) ============
Write-Step "1/3 Avvio database (PostgreSQL + MinIO + Redis)"
docker compose up -d db minio redis
if ($LASTEXITCODE -ne 0) {
    Write-Err "Errore nell'avvio dei container Docker"
    exit 1
}

# Aspetta che PostgreSQL sia pronto
Write-Host "  Attendo che il database sia pronto..." -ForegroundColor Gray
$maxWait = 30
$waited = 0
do {
    Start-Sleep -Seconds 2
    $waited += 2
    $pgReady = docker compose exec -T db pg_isready -U postgres 2>&1
    if ($pgReady -match "accepting connections") {
        Write-Ok "Database pronto"
        break
    }
    if ($waited -ge $maxWait) {
        Write-Warn "Timeout attesa database, provo a continuare comunque"
        break
    }
} while ($true)

# ============ 2. BACKEND (NUOVA FINESTRA) ============
Write-Step "2/3 Avvio backend FastAPI"

$backendCmd = @"
cd '$ROOT\backend'
& '.\.venv\Scripts\Activate.ps1'
Write-Host 'BACKEND — Cognitive Assessment Platform' -ForegroundColor Cyan
Write-Host 'Docs Swagger: http://localhost:8000/docs' -ForegroundColor Green
Write-Host 'Per fermare: chiudi questa finestra o premi Ctrl+C' -ForegroundColor Yellow
Write-Host ''
uvicorn app.main:app --reload --port 8000
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Write-Ok "Backend avviato in una nuova finestra (http://localhost:8000)"

# Aspetta che il backend risponda
Write-Host "  Attendo che il backend sia pronto..." -ForegroundColor Gray
$maxWait = 30
$waited = 0
do {
    Start-Sleep -Seconds 2
    $waited += 2
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 2>&1
        if ($resp.StatusCode -eq 200) {
            Write-Ok "Backend risponde"
            break
        }
    } catch {
        # ancora non pronto
    }
    if ($waited -ge $maxWait) {
        Write-Warn "Il backend ci sta mettendo piu' del previsto, controlla la sua finestra"
        break
    }
} while ($true)

# ============ 3. FRONTEND (NUOVA FINESTRA) ============
Write-Step "3/3 Avvio frontend React"

$frontendCmd = @"
cd '$ROOT\frontend'
Write-Host 'FRONTEND — Cognitive Assessment Platform' -ForegroundColor Cyan
Write-Host 'App: http://localhost:5173' -ForegroundColor Green
Write-Host 'Per fermare: chiudi questa finestra o premi Ctrl+C' -ForegroundColor Yellow
Write-Host ''
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
Write-Ok "Frontend avviato in una nuova finestra (http://localhost:5173)"

# Aspetta un attimo e apri il browser
Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"
Start-Process "http://localhost:8000/docs"

Write-Host "`n############################################################" -ForegroundColor Green
Write-Host "#  PROGETTO AVVIATO                                        #" -ForegroundColor Green
Write-Host "############################################################" -ForegroundColor Green
Write-Host "`nServizi attivi:" -ForegroundColor Cyan
Write-Host "  - Frontend (app medico):  http://localhost:5173" -ForegroundColor White
Write-Host "  - Backend API + Swagger:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Database PostgreSQL:    localhost:5432" -ForegroundColor White
Write-Host "  - MinIO (storage audio):  http://localhost:9001" -ForegroundColor White
Write-Host "`nIl backend e il frontend girano nelle DUE finestre PowerShell appena aperte." -ForegroundColor Gray
Write-Host "Per FERMARE tutto, lancia stop.ps1 (o chiudi le finestre + 'docker compose down')." -ForegroundColor Gray
Write-Host ""
