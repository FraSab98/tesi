<#
.SYNOPSIS
    Setup iniziale del progetto Cognitive Assessment Platform (eseguire UNA SOLA VOLTA).
.DESCRIPTION
    - Verifica prerequisiti (Python, Node, Docker)
    - Crea il virtual environment Python
    - Installa le dipendenze backend (incluse quelle ML della Fase 6)
    - Scarica il modello spaCy italiano
    - Installa le dipendenze frontend
    - Crea il file .env se non esiste
.NOTES
    Lanciare da PowerShell nella cartella radice del progetto (dove c'e' la cartella backend\ e frontend\).
    Se ricevi un errore sui permessi di esecuzione, lancia prima:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

$ErrorActionPreference = "Stop"

# Colori per output leggibile
function Write-Step    { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok      { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err     { param($msg) Write-Host "  [X]  $msg" -ForegroundColor Red }

Write-Host "############################################################" -ForegroundColor Magenta
Write-Host "#  SETUP — Cognitive Assessment Platform                   #" -ForegroundColor Magenta
Write-Host "#  Da eseguire una sola volta                              #" -ForegroundColor Magenta
Write-Host "############################################################" -ForegroundColor Magenta

# ============ 1. VERIFICA PREREQUISITI ============
Write-Step "1/6 Verifica prerequisiti"

# Python
try {
    $pyVersion = (python --version 2>&1).ToString()
    if ($pyVersion -match "Python 3\.(1[1-9]|[2-9]\d)") {
        Write-Ok "$pyVersion trovato"
    } else {
        Write-Err "Serve Python 3.11+. Trovato: $pyVersion"
        Write-Host "  Scarica da https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Err "Python non trovato nel PATH. Installalo da https://www.python.org/downloads/"
    exit 1
}

# Node
try {
    $nodeVersion = (node --version 2>&1).ToString()
    if ($nodeVersion -match "v(2[0-9]|[3-9]\d)") {
        Write-Ok "Node $nodeVersion trovato"
    } else {
        Write-Warn "Node $nodeVersion: consigliato v20+. Potrebbe funzionare comunque."
    }
} catch {
    Write-Err "Node.js non trovato. Installalo da https://nodejs.org/"
    exit 1
}

# Docker
try {
    docker --version | Out-Null
    Write-Ok "Docker trovato"
    # Verifica che il daemon sia attivo
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker e' installato ma il daemon non e' attivo. Apri Docker Desktop e riprova."
        exit 1
    }
    Write-Ok "Docker daemon attivo"
} catch {
    Write-Err "Docker non trovato. Installa Docker Desktop da https://www.docker.com/products/docker-desktop/"
    exit 1
}

# ============ 2. VIRTUAL ENVIRONMENT ============
Write-Step "2/6 Creazione virtual environment Python"
Push-Location backend
if (-Not (Test-Path ".venv")) {
    python -m venv .venv
    Write-Ok "Virtual environment creato in backend\.venv"
} else {
    Write-Ok "Virtual environment gia' esistente"
}

# Attiva il venv
& ".\.venv\Scripts\Activate.ps1"
Write-Ok "Virtual environment attivato"

# ============ 3. DIPENDENZE BACKEND ============
Write-Step "3/6 Installazione dipendenze backend (puo' richiedere diversi minuti)"
python -m pip install --upgrade pip --quiet
Write-Host "  Installazione requirements base..." -ForegroundColor Gray
pip install -r requirements.txt --quiet
Write-Ok "Dipendenze base installate"

# Dipendenze ML pesanti (Fase 6) - se il file esiste
if (Test-Path "requirements-analysis.txt") {
    Write-Warn "Installazione dipendenze ML (~5 GB, puo' richiedere 10-20 minuti)..."
    pip install -r requirements-analysis.txt --quiet
    Write-Ok "Dipendenze ML installate"
} else {
    Write-Warn "requirements-analysis.txt non trovato, salto le dipendenze ML"
}

# ============ 4. MODELLO SPACY ITALIANO ============
Write-Step "4/6 Download modello spaCy italiano"
try {
    python -m spacy download it_core_news_lg
    Write-Ok "Modello it_core_news_lg installato"
} catch {
    Write-Warn "Download spaCy fallito (lo puoi rifare manualmente dopo)"
}
Pop-Location

# ============ 5. DIPENDENZE FRONTEND ============
Write-Step "5/6 Installazione dipendenze frontend"
Push-Location frontend
npm install
# recharts e' necessario per i grafici della Fase 7
npm install recharts --save
Write-Ok "Dipendenze frontend installate"
Pop-Location

# ============ 6. FILE .ENV ============
Write-Step "6/6 Configurazione file .env"
if (-Not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Ok "File .env creato da .env.example"
        Write-Warn "IMPORTANTE: apri il file .env e inserisci la tua ANTHROPIC_API_KEY"
        Write-Host "  Ottienila su https://console.anthropic.com/" -ForegroundColor Yellow
    } else {
        Write-Warn ".env.example non trovato, crea .env manualmente"
    }
} else {
    Write-Ok "File .env gia' esistente"
}

Write-Host "`n############################################################" -ForegroundColor Green
Write-Host "#  SETUP COMPLETATO                                        #" -ForegroundColor Green
Write-Host "############################################################" -ForegroundColor Green
Write-Host "`nProssimi passi:" -ForegroundColor Cyan
Write-Host "  1. Apri il file .env e inserisci ANTHROPIC_API_KEY" -ForegroundColor White
Write-Host "  2. Lancia start.ps1 per avviare il progetto" -ForegroundColor White
Write-Host ""
