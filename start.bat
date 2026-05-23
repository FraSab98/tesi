@echo off
REM ============================================================
REM  AVVIO - Cognitive Assessment Platform (versione .bat)
REM  Alternativa a start.ps1 per chi preferisce il doppio click.
REM  Esegui prima setup.ps1 una sola volta.
REM ============================================================

echo ############################################################
echo #  AVVIO - Cognitive Assessment Platform                   #
echo ############################################################
echo.

REM Vai nella cartella dello script
cd /d "%~dp0"

REM ---- Controllo Docker ----
docker ps >nul 2>&1
if errorlevel 1 (
    echo [X] Docker non e' attivo. Apri Docker Desktop e riprova.
    pause
    exit /b 1
)
echo [OK] Docker attivo

REM ---- Controllo .env ----
if not exist ".env" (
    echo [X] File .env mancante. Lancia prima setup.ps1
    pause
    exit /b 1
)
echo [OK] File .env trovato

REM ---- Controllo venv ----
if not exist "backend\.venv" (
    echo [X] Virtual environment mancante. Lancia prima setup.ps1
    pause
    exit /b 1
)
echo [OK] Virtual environment trovato

REM ============ 1. DATABASE ============
echo.
echo === 1/3 Avvio database (PostgreSQL + MinIO + Redis) ===
docker compose up -d db minio redis
if errorlevel 1 (
    echo [X] Errore avvio Docker
    pause
    exit /b 1
)
echo [OK] Database avviato
echo Attendo 8 secondi che il database sia pronto...
timeout /t 8 /nobreak >nul

REM ============ 2. BACKEND ============
echo.
echo === 2/3 Avvio backend FastAPI (nuova finestra) ===
start "BACKEND - Cognitive Platform" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\activate.bat && echo Backend in avvio su http://localhost:8000/docs && uvicorn app.main:app --reload --port 8000"
echo [OK] Backend avviato
echo Attendo 10 secondi che il backend sia pronto...
timeout /t 10 /nobreak >nul

REM ============ 3. FRONTEND ============
echo.
echo === 3/3 Avvio frontend React (nuova finestra) ===
start "FRONTEND - Cognitive Platform" cmd /k "cd /d "%~dp0frontend" && echo Frontend in avvio su http://localhost:5173 && npm run dev"
echo [OK] Frontend avviato
echo Attendo 5 secondi...
timeout /t 5 /nobreak >nul

REM ---- Apri il browser ----
start http://localhost:5173
start http://localhost:8000/docs

echo.
echo ############################################################
echo #  PROGETTO AVVIATO                                        #
echo ############################################################
echo.
echo Servizi attivi:
echo   - Frontend (app medico):  http://localhost:5173
echo   - Backend API + Swagger:  http://localhost:8000/docs
echo   - Database PostgreSQL:    localhost:5432
echo.
echo Backend e frontend girano nelle due finestre appena aperte.
echo Per fermare tutto: chiudi le finestre e lancia "docker compose down"
echo.
pause
