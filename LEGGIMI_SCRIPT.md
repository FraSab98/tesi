# Script di avvio — Cognitive Assessment Platform (Windows)

Questi script automatizzano l'avvio dell'intero progetto su Windows con Docker.

## Dove mettere gli script

Copia i 4 file nella **cartella radice del progetto**, quella che contiene le sottocartelle `backend\` e `frontend\` e il file `docker-compose.yml`:

```
tesi\
├── backend\
├── frontend\
├── docker-compose.yml
├── .env.example
├── setup.ps1        ← metti qui
├── start.ps1        ← metti qui
├── stop.ps1         ← metti qui
└── start.bat        ← metti qui
```

## Uso in 3 passi

### Passo 1 — Setup (UNA SOLA VOLTA)

Apri **PowerShell** nella cartella del progetto (Shift + tasto destro → "Apri finestra PowerShell qui") e lancia:

```powershell
# Se ricevi un errore sui permessi, lancia prima questo:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Poi il setup vero e proprio:
.\setup.ps1
```

Questo script:
- Verifica Python, Node, Docker
- Crea il virtual environment Python
- Installa TUTTE le dipendenze (incluse quelle ML della Fase 6, ~5 GB — pazienta 10-20 minuti)
- Scarica il modello spaCy italiano
- Installa le dipendenze frontend
- Crea il file `.env`

### Passo 2 — Inserisci la API key

Apri il file `.env` con il Blocco Note e inserisci la tua chiave Anthropic:

```
ANTHROPIC_API_KEY=sk-ant-la-tua-chiave-qui
```

(La ottieni gratis su https://console.anthropic.com/)

### Passo 3 — Avvia il progetto

Ogni volta che vuoi usare il progetto:

```powershell
.\start.ps1
```

Oppure fai **doppio click su `start.bat`**.

Lo script:
- Avvia il database (Docker)
- Apre il backend in una finestra
- Apre il frontend in un'altra finestra
- Apre automaticamente il browser su http://localhost:5173

## Per fermare tutto

```powershell
.\stop.ps1
```

Oppure chiudi manualmente le due finestre PowerShell e lancia `docker compose down`.

## Servizi e porte

| Servizio | URL | Cosa fa |
|----------|-----|---------|
| Frontend | http://localhost:5173 | App per il medico |
| Backend + Swagger | http://localhost:8000/docs | API e documentazione |
| PostgreSQL | localhost:5432 | Database |
| MinIO console | http://localhost:9001 | Storage file audio (user/pass: minioadmin) |

## Risoluzione problemi

**"setup.ps1 cannot be loaded because running scripts is disabled"**
Lancia prima: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

**"Docker non e' attivo"**
Apri Docker Desktop (l'applicazione) e aspetta che sia completamente avviato, poi rilancia lo script.

**Il backend si apre ma da' errori di import**
Probabilmente non hai unito correttamente i file delle fasi 6 e 7. Verifica che in `backend\app\` ci siano le cartelle `analysis\`, `tasks\`, `reporting\`, `longitudinal\`, e che `main.py` includa i router `analysis` e `reports`.

**Il backend dice "ANTHROPIC_API_KEY non impostata"**
Apri `.env` e verifica che la chiave sia corretta, senza spazi o virgolette.

**Le dipendenze ML danno errore durante il setup**
Le librerie come torch sono pesanti. Se il setup si blocca, puoi installarle a mano dentro il venv attivato:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-analysis.txt
```

**La prima generazione di test e' lentissima**
Normale: i modelli Whisper/spaCy/BERT vengono caricati in memoria al primo uso. Dalle volte successive e' molto piu' veloce.

## Avvio rapido senza ML (alternativa leggera)

Se vuoi solo testare la parte base (somministrazione test + scoring) senza aspettare il download dei 5 GB di modelli ML, puoi:

1. Nel setup, salta `requirements-analysis.txt` (commenta la riga o rispondi di no)
2. La piattaforma funziona lo stesso per CPT, Digit Span, Stroop, Go/No-Go
3. Solo l'analisi multi-canale audio (Fase 6) non sara' disponibile

Il sistema e' progettato con "graceful degradation": se i moduli ML non ci sono, il resto funziona comunque.
