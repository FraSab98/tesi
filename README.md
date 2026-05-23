# Piattaforma di Valutazione Cognitiva — MVP

> **Tesi Magistrale in Informatica**
> Valutazione delle malattie cognitive mediante approccio di Sentiment Analysis
> Relatore: [Nome] · Dipartimento di Informatica

Piattaforma web per la somministrazione di test neuropsicologici interattivi generati dinamicamente tramite Large Language Model. L'MVP implementa quattro test clinicamente validati (CPT, Digit Span, Stroop, Go/No-Go) e una pipeline di scoring basata sulla letteratura scientifica analizzata nello stato dell'arte.

## Cosa fa il sistema

1. **Il medico** configura una batteria di test tramite una dashboard web, specificando il profilo del paziente e i parametri di ciascun test (lingua, difficoltà, durata).
2. Il **backend** invoca un LLM (Claude Sonnet via API oppure Llama locale) per generare gli stimoli specifici del test, validati automaticamente contro schemi Pydantic rigorosi.
3. Il **paziente** accede tramite un link personale ed esegue i test nel browser, con timing preciso al millisecondo.
4. La **pipeline di scoring** calcola indicatori cognitivi (tempo di reazione, variabilità, Levenshtein distance per Digit Span, interference score per Stroop, risk score per Go/No-Go).
5. Il medico riceve un report con i punteggi e le metriche secondo gli standard dei paper di riferimento.

## Architettura

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Frontend React │────▶│  FastAPI Backend │────▶│  PostgreSQL  │
│  (medico +      │     │  + LLM layer     │     │              │
│   paziente)     │     │  + scoring       │     └──────────────┘
└─────────────────┘     └────────┬─────────┘
                                 │
                          ┌──────┴──────┐
                          ▼             ▼
                    ┌──────────┐  ┌──────────┐
                    │  Claude  │  │  Ollama  │
                    │  (API)   │  │ (locale) │
                    └──────────┘  └──────────┘
```

## Stack tecnologico

| Livello | Tecnologia |
|---------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.11 + FastAPI + SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 15 |
| LLM | Anthropic Claude (API) / Ollama + Llama (locale) |
| Storage audio | MinIO (S3-compatible) |
| Validazione | Pydantic v2 |
| Deploy | Docker Compose |

## Struttura del progetto

```
fase2/
├── backend/
│   ├── app/
│   │   ├── main.py                   # entry point FastAPI
│   │   ├── core/                     # config, database, security
│   │   ├── api/                      # endpoint REST
│   │   ├── llm/                      # provider Claude e Ollama
│   │   ├── schemas/                  # schemi Pydantic (cat A-G)
│   │   ├── services/tests/           # generator per ogni test
│   │   ├── scoring/                  # algoritmi di scoring
│   │   └── models/                   # ORM SQLAlchemy
│   ├── tests/                        # unit test pytest
│   ├── demo_end_to_end.py           # demo standalone
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/client.ts             # wrapper API
│   │   ├── components/
│   │   │   ├── DoctorDashboard.tsx
│   │   │   └── SessionRunner.tsx
│   │   ├── tests/                    # runner per ogni test
│   │   │   ├── CPTRunner.tsx
│   │   │   ├── DigitSpanRunner.tsx
│   │   │   ├── StroopRunner.tsx
│   │   │   └── GoNoGoRunner.tsx
│   │   └── utils/timing.ts
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── Fase1_Organizzazione_Informazioni.docx
│   └── Fase2_Architettura_Sviluppo.docx
├── docker-compose.yml
├── .env.example
└── README.md
```

## Setup rapido

### Prerequisiti
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (opzionale ma raccomandato)
- API key Anthropic **oppure** Ollama installato in locale

### 1. Clona e prepara l'ambiente
```bash
git clone <repo-url> tesi
cd tesi/fase2
cp .env.example .env
# Modifica .env e imposta ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Avvio con Docker (consigliato)
```bash
docker compose up -d db minio redis
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In un altro terminale:
```bash
cd frontend
npm install
npm run dev
```

Apri http://localhost:5173

### 3. Verifica installazione — demo standalone
Lancia la demo che mostra l'intera pipeline senza bisogno di frontend, DB o API key:
```bash
cd backend
python demo_end_to_end.py
```

Output atteso: generazione CPT e Go/No-Go, simulazione di 3 profili di paziente (healthy, MCI, ADHD), scoring comparativo.

### 4. Test automatici
```bash
cd backend
python -m pytest tests/ -v
# 26 passed
```

## Utilizzo tipico

### Come medico
1. Vai su http://localhost:5173
2. Inserisci codice paziente, età e lingua
3. Seleziona i test da somministrare (CPT, Digit Span, Stroop, Go/No-Go)
4. Clicca "Crea sessione": il backend chiama l'LLM per generare gli stimoli
5. Copia il link per il paziente o avvia direttamente la sessione

### Come paziente
1. Apri il link ricevuto
2. Segui le istruzioni a schermo per ogni test
3. Al termine della sessione, i dati vengono inviati automaticamente al medico

## Configurazione LLM

### Modalità API cloud (Claude)
```bash
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-5
```

### Modalità locale (Llama via Ollama)
```bash
# Installa Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b

# .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

Il sistema è progettato per switchare tra i due provider senza modifiche al codice: tutti i generator usano l'interfaccia astratta `LLMProvider`.

## Test implementati nell'MVP

| Test | Categoria | Paper di riferimento | Generazione |
|------|-----------|----------------------|-------------|
| **CPT** | A — Stimolo reattivo semplice | Advokat et al. 2007 | Procedurale |
| **Digit Span** | C — Sequenza da ripetere | Asgari et al. 2020 | LLM |
| **Stroop** | B — Stimolo con conflitto | van Mourik et al. 1998 | LLM |
| **Go/No-Go** | A — Con inibizione | Watanabe et al. 2024 | Procedurale |

## Metriche di scoring

Ogni test produce indicatori specifici secondo i paper:

- **CPT**: omissioni, commissioni, RT medio, variabilità RT, attention score composito
- **Digit Span**: oltre al punteggio convenzionale, l'approccio Levenshtein di Asgari (più sensibile a MCI precoce) con conteggio di inserzioni/cancellazioni/sostituzioni
- **Stroop**: interference score classico (C−CW) e Golden (CW − WC/(W+C))
- **Go/No-Go**: miss, mistake, screening risk score basato sui cut-off MoCA/MMSE del paper Watanabe

## Validazione LLM con retry automatico

Ogni stimolo generato dall'LLM è validato contro uno schema Pydantic con vincoli specifici (es. CPT: mai più di 3 target consecutivi; Digit Span: no progressioni aritmetiche; Stroop: word ≠ ink_color in condizione incongruente). In caso di output non conforme, il sistema riprova fino a 3 volte arricchendo il prompt con l'errore specifico.

## Roadmap Fase 6+

- [ ] Trascrizione audio con Whisper (per Digit Span vocale)
- [ ] Feature linguistiche con spaCy (diversità lessicale, coesione — come Paper 11)
- [ ] Feature prosodiche con librosa (pitch, energia, MFCC)
- [ ] Sentiment ed emotion analysis con modelli HuggingFace italiani
- [ ] Dashboard report con grafici (recharts)
- [ ] Export PDF dei report per il medico
- [ ] Integrazione completa Ollama e capitolo di tesi comparativo

## Risorse documentali

- `docs/Fase1_Organizzazione_Informazioni.docx` — catalogazione test, categorie di domanda, parametri (50+ pagine)
- `docs/Fase2_Architettura_Sviluppo.docx` — architettura, stack, prompt engineering, roadmap
- Documentazione API automatica: `http://localhost:8000/docs` (Swagger UI)

## Licenza

Codice prodotto per tesi magistrale. Uso accademico e di ricerca.
