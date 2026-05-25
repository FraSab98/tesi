# Documentazione Tecnica del Progetto
## Piattaforma di Valutazione Cognitiva Multicanale

Questo documento descrive, file per file, l'intero codice sorgente della piattaforma.
Per ciascun file sono indicati lo **scopo** (a cosa serve all'interno del sistema) e
una sintesi di **cosa fa** (responsabilità e contenuti principali). La documentazione è
organizzata per moduli funzionali, rispecchiando la struttura delle cartelle del repository.

Sono volutamente esclusi gli artefatti non sorgente (ambienti virtuali `.venv`, dipendenze
`node_modules`, cache `__pycache__`, file di lock), in quanto generati automaticamente e non
parte del contributo progettuale.

---

## 1. Panoramica dell'architettura

Il sistema è una piattaforma a livelli composta da:

- un **backend** in Python/FastAPI che espone un'API REST asincrona, orchestra la logica di
  dominio (gestione di pazienti e sessioni, generazione degli stimoli, scoring delle prove,
  analisi multicanale del linguaggio, reportistica e analisi longitudinale) e si interfaccia
  con un database PostgreSQL e con i servizi di intelligenza artificiale;
- un **frontend** in React/TypeScript che fornisce la dashboard del clinico e le interfacce di
  somministrazione delle prove al paziente;
- un livello di **infrastruttura** (Docker Compose e script di avvio) per l'esecuzione locale
  dell'intero stack.

```
tesi/
├── backend/            # servizio applicativo FastAPI
│   └── app/
│       ├── core/       # configurazione e accesso al database
│       ├── models/     # modelli ORM (tabelle del database)
│       ├── schemas/    # schemi di validazione (API e singoli test)
│       ├── llm/        # provider dei modelli linguistici (Claude/Ollama)
│       ├── services/   # generatori degli stimoli dei test
│       ├── scoring/    # calcolo dei punteggi delle prove cognitive
│       ├── analysis/   # pipeline di analisi multicanale del linguaggio
│       ├── tasks/      # orchestrazione delle analisi (sincrone/asincrone)
│       ├── reporting/  # aggregazione del report e generazione PDF
│       ├── longitudinal/  # analisi dei trend tra sessioni
│       └── api/        # endpoint REST
├── frontend/           # applicazione React/TypeScript
│   └── src/
│       ├── components/ # pagine e componenti della dashboard
│       ├── tests/      # interfacce di somministrazione delle prove
│       ├── api/        # client HTTP verso il backend
│       ├── styles/     # design system
│       └── utils/      # utilità (timing ad alta precisione)
└── (infrastruttura)    # docker-compose, script di avvio, configurazioni
```

---

## 2. Backend

### 2.1 Avvio e configurazione

#### `backend/app/main.py`
**Scopo.** Punto di ingresso dell'applicazione FastAPI.
**Cosa fa.** Crea l'istanza dell'applicazione, configura il logging e il middleware CORS,
registra i router degli endpoint (pazienti, sessioni, risposte, analisi, report) sotto il
prefisso dell'API. Gestisce il ciclo di vita dell'applicazione (`lifespan`): in modalità di
sviluppo inizializza automaticamente lo schema del database all'avvio.

#### `backend/app/core/config.py`
**Scopo.** Configurazione centralizzata, basata su variabili d'ambiente.
**Cosa fa.** Definisce la classe `Settings` (pydantic-settings) che legge il file `.env`:
nome applicazione, prefisso API, URL del database, provider LLM e relative credenziali/modelli,
parametri di storage e di sicurezza. Espone l'istanza `settings` e la factory
`get_llm_provider()` che istanzia il provider LLM configurato (Anthropic od Ollama).

#### `backend/app/core/database.py`
**Scopo.** Configurazione dell'accesso al database.
**Cosa fa.** Inizializza il motore SQLAlchemy 2.0 asincrono e la *session factory*, con
pool di connessioni e *pre-ping*. Definisce la classe `Base` per i modelli ORM, la dependency
`get_db()` (che fornisce una sessione transazionale con commit/rollback automatici) e
`init_db()` per la creazione dello schema.

### 2.2 Modelli dati

#### `backend/app/models/__init__.py`
**Scopo.** Definizione delle tabelle del database (modelli ORM).
**Cosa fa.** Dichiara le entità del dominio e le loro relazioni: `Patient` (paziente),
`Session` (sessione di valutazione), `TestConfiguration` (configurazione di una prova nella
sessione), `GeneratedStimulus` (stimoli generati per una prova), `Response` (risposta del
paziente a uno stimolo), `CognitiveScore` (punteggi calcolati di una prova) e `AnalysisResult`
(esito dell'analisi multicanale). Include la funzione `_uuid()` per le chiavi primarie.

### 2.3 Schemi di validazione

#### `backend/app/schemas/api.py`
**Scopo.** Schemi (Pydantic) di input/output dell'API REST.
**Cosa fa.** Definisce i contratti dati scambiati con il frontend: creazione e lettura di
pazienti (`PatientCreate`, `PatientRead`), creazione e composizione di sessioni
(`SessionCreate`, `TestConfigInSession`, `SessionBuild`, `SessionRead`, `SessionWithTests`),
lettura degli stimoli (`StimulusRead`), invio delle risposte (`ResponseSubmit`,
`ResponseBatchSubmit`), lettura dei punteggi (`ScoreRead`) e struttura del report di sessione
(`SessionReport`).

#### `backend/app/schemas/cpt.py`
**Scopo.** Schemi del Continuous Performance Test (CPT).
**Cosa fa.** Definisce `CPTStimulus`, `CPTSequence` e `CPTConfig` con regole di validazione
(normalizzazione delle lettere, vincoli sulla sequenza di stimoli, intervalli inter-stimolo,
conteggio totale degli stimoli) che garantiscono la correttezza della prova generata.

#### `backend/app/schemas/digit_span.py`
**Scopo.** Schemi del test di memoria di lavoro (Digit Span).
**Cosa fa.** Definisce `DigitSpanSequence`, `DigitSpanBatch` e `DigitSpanConfig`, con
validazioni sull'intervallo delle cifre, sul limite di ripetizioni, sull'assenza di pattern
banali e sulla distribuzione bilanciata delle cifre.

#### `backend/app/schemas/stroop.py`
**Scopo.** Schemi del test di interferenza (Stroop, color-word).
**Cosa fa.** Definisce `StroopStimulus`, `StroopBlock` e `StroopConfig`, con validazioni di
coerenza tra parola e colore, corrispondenza tra stimoli e condizione del blocco e
distribuzione bilanciata dei colori.

#### `backend/app/schemas/go_nogo.py`
**Scopo.** Schemi del test di controllo inibitorio (Go/No-Go).
**Cosa fa.** Definisce `GoNoGoTrial`, `GoNoGoPhase`, `GoNoGoTest` e `GoNoGoConfig`, con
validazioni sul conteggio dei trial, sulla coerenza dei colori per tipo, sull'assenza di
sequenze troppo lunghe dello stesso tipo e sulla corretta inversione dei colori nella fase
*reverse*.

#### `backend/app/schemas/narrative.py`
**Scopo.** Schemi della prova narrativa (risposta verbale libera).
**Cosa fa.** Definisce `NarrativeConfig` e `NarrativePrompt` e il repertorio di spunti
narrativi (`NARRATIVE_PROMPT_POOL`): tipologie di consegna (descrizione di immagine, racconto
della giornata ideale, routine quotidiana, ripetizione di una storia), lingua e modalità di
risposta. La risposta non viene convertita in punteggio ma alimenta la pipeline multicanale.

### 2.4 Provider dei modelli linguistici (LLM)

#### `backend/app/llm/provider.py`
**Scopo.** Interfaccia astratta comune ai provider LLM.
**Cosa fa.** Definisce la classe astratta `LLMProvider` con i metodi `generate_structured`
(output JSON conforme a uno schema Pydantic), `generate_text` (testo libero) e la proprietà
`provider_name`. Consente di sostituire il modello sottostante senza modificare i generatori.

#### `backend/app/llm/anthropic_provider.py`
**Scopo.** Implementazione del provider basata su Claude (API Anthropic).
**Cosa fa.** Implementa `LLMProvider` sfruttando il meccanismo di *tool use* per ottenere
output JSON strutturato e validato; gestisce i tentativi ripetuti (retry) in caso di output
non conforme.

#### `backend/app/llm/ollama_provider.py`
**Scopo.** Implementazione del provider basata su modelli locali (Ollama).
**Cosa fa.** Implementa `LLMProvider` per modelli eseguiti localmente (es. Llama 3.1),
forzando l'output in formato JSON e validandolo con Pydantic, con retry in caso di errore.
Consente l'esecuzione del sistema senza dipendere da servizi esterni.

### 2.5 Generatori degli stimoli

#### `backend/app/services/tests/base.py`
**Scopo.** Classe base astratta dei generatori di prove (pattern *template method*).
**Cosa fa.** Definisce `TestGenerator`, che standardizza il flusso di generazione di una prova:
costruzione dei prompt di sistema e utente, schema di output, parametri (temperatura, token) e
metodo `generate()`. Le sottoclassi specializzano il comportamento per ciascun test.

#### `backend/app/services/tests/cpt_generator.py`
**Scopo.** Generatore del Continuous Performance Test.
**Cosa fa.** Produce la sequenza di stimoli del CPT, distribuendo le posizioni dei target ed
evitando ripetizioni indesiderate; può operare in modo procedurale senza necessità di LLM.

#### `backend/app/services/tests/digit_span_generator.py`
**Scopo.** Generatore del test Digit Span.
**Cosa fa.** Costruisce i batch di sequenze numeriche di lunghezza crescente secondo la
configurazione, predisponendo i prompt per l'eventuale generazione assistita da LLM.

#### `backend/app/services/tests/stroop_generator.py`
**Scopo.** Generatore del test di Stroop.
**Cosa fa.** Genera i blocchi di stimoli nelle diverse condizioni (lettura della parola,
denominazione del colore, condizione incongruente parola-colore), bilanciando la
distribuzione dei colori.

#### `backend/app/services/tests/go_nogo_generator.py`
**Scopo.** Generatore del task Go/No-Go.
**Cosa fa.** Costruisce le fasi della prova (formazione, differenziazione, inversione),
bilanciando i trial Go/No-Go ed evitando sequenze ripetitive; può procedere in modo
procedurale.

#### `backend/app/services/tests/narrative_generator.py`
**Scopo.** Generatore della prova narrativa.
**Cosa fa.** Seleziona uno spunto narrativo dal repertorio in base alla configurazione e
predispone lo stimolo testuale per il soggetto; non richiede LLM per la generazione.

### 2.6 Calcolo dei punteggi (scoring)

#### `backend/app/scoring/cpt_scorer.py`
**Scopo.** Calcolo dei punteggi del CPT.
**Cosa fa.** A partire dalle risposte, calcola tempi di reazione, variabilità, tassi di
omissione e commissione e un punteggio di attenzione complessivo, oltre a un indice di
instabilità attentiva.

#### `backend/app/scoring/digit_span_scorer.py`
**Scopo.** Calcolo dei punteggi del Digit Span.
**Cosa fa.** Confronta le sequenze fornite con quelle attese (anche tramite distanza di
edit/Levenshtein), determinando lo *span* corretto più lungo e metriche di accuratezza
graduata per ciascun item.

#### `backend/app/scoring/stroop_scorer.py`
**Scopo.** Calcolo dei punteggi dello Stroop.
**Cosa fa.** Calcola accuratezza e tempi per ciascun blocco e l'effetto di interferenza
(differenza di tempo tra condizione congruente e incongruente).

#### `backend/app/scoring/go_nogo_scorer.py`
**Scopo.** Calcolo dei punteggi del Go/No-Go.
**Cosa fa.** Per ciascuna fase calcola errori di omissione e commissione, tempi di reazione e
un punteggio di rischio di screening, sintetizzando il controllo inibitorio del soggetto.

### 2.7 Pipeline di analisi multicanale

#### `backend/app/analysis/transcription.py`
**Scopo.** Trascrizione automatica del parlato (ASR).
**Cosa fa.** Incapsula il modello Whisper per convertire l'audio in testo; fornisce inoltre
una funzione di interpretazione di sequenze numeriche dette a voce (utile al Digit Span).

#### `backend/app/analysis/linguistic.py`
**Scopo.** Analisi linguistica del testo.
**Cosa fa.** Tramite spaCy (modello italiano) estrae metriche di fluenza, ricchezza lessicale
(diversità lessicale, MATTR), densità lessicale, coesione, complessità sintattica (profondità
media dell'albero) e distribuzione delle categorie grammaticali, restituite in
`LinguisticFeatures`.

#### `backend/app/analysis/prosodic.py`
**Scopo.** Analisi prosodica del segnale vocale.
**Cosa fa.** Tramite librosa estrae caratteristiche acustiche del parlato (ritmo, pause,
energia, andamento) dal file audio, restituite in `ProsodicFeatures`. È attiva solo per le
risposte vocali.

#### `backend/app/analysis/sentiment_emotion.py`
**Scopo.** Analisi affettiva del testo.
**Cosa fa.** Tramite modelli Transformer per l'italiano classifica la polarità affettiva
(`SentimentAnalyzer` → `SentimentResult`) e le emozioni discrete prevalenti
(`EmotionAnalyzer` → `EmotionResult`).

#### `backend/app/analysis/multichannel.py`
**Scopo.** Orchestrazione e sintesi dell'analisi multicanale.
**Cosa fa.** Coordina i canali (linguistico, prosodico, sentiment, emozione) tramite
`MultiChannelAnalyzer`, sia su testo sia su audio, e calcola i tre indicatori compositi:
*Cognitive Strain* (sforzo cognitivo), *Emotional Distress* (disagio emotivo) e
*Communication Quality* (qualità della comunicazione), restituiti in `MultiChannelAnalysis`.

### 2.8 Orchestrazione delle analisi

#### `backend/app/tasks/analysis_tasks.py`
**Scopo.** Funzioni di esecuzione della pipeline di analisi.
**Cosa fa.** Costruisce l'analizzatore multicanale ed espone le funzioni `analyze_text_response`
e `analyze_audio_response`, invocabili in modo sincrono o in background, restituendo il
dizionario completo dei risultati da persistere.

### 2.9 Reportistica

#### `backend/app/reporting/aggregator.py`
**Scopo.** Aggregazione dei dati di una sessione in un report strutturato.
**Cosa fa.** `ReportAggregator` riassume i punteggi delle prove, sintetizza i risultati
multicanale, calcola il punteggio cognitivo complessivo e determina il livello di rischio
(con pesatura dei segnali e gestione delle sessioni di sola analisi), producendo flag, osservazioni e
raccomandazioni.

#### `backend/app/reporting/pdf_generator.py`
**Scopo.** Generazione del report in formato PDF.
**Cosa fa.** Tramite reportlab compone il documento (intestazione, dati paziente, sintesi del
rischio, risultati per test, sezione multicanale e dettaglio per analisi con trascrizione,
profilo linguistico, prosodico ed emotivo, osservazioni e raccomandazioni).

### 2.10 Analisi longitudinale

#### `backend/app/longitudinal/analyzer.py`
**Scopo.** Analisi dell'andamento del paziente su più sessioni.
**Cosa fa.** `LongitudinalAnalyzer` estrae serie temporali per le metriche cognitive e per gli
indicatori multicanale, ne calcola il trend (regressione lineare, direzione, *Reliable Change
Index*), genera alert clinici e una sintesi testuale. Lo score cognitivo è tracciato solo per
le sessioni che includono prove cognitive, mentre gli indicatori multicanale sono tracciati
per tutte le sessioni dotate di analisi.

### 2.11 Endpoint REST (API)

#### `backend/app/api/patients.py`
**Scopo.** Gestione dei pazienti e alimentazione dell'analisi longitudinale.
**Cosa fa.** Espone la creazione e l'elenco dei pazienti e l'endpoint che restituisce i report
strutturati di tutte le sessioni di un paziente dotate di dati (punteggi o analisi), utilizzati
dall'analisi longitudinale.

#### `backend/app/api/sessions.py`
**Scopo.** Creazione e gestione delle sessioni di valutazione.
**Cosa fa.** Espone la composizione di una sessione (selezione delle prove e generazione degli
stimoli tramite il registro dei test, comprensivo della prova narrativa), l'elenco delle
sessioni con i relativi indicatori di completamento (numero di punteggi e di analisi) e
l'endpoint che costruisce il report di una sessione integrando punteggi e analisi multicanale.

#### `backend/app/api/responses.py`
**Scopo.** Acquisizione delle risposte del paziente.
**Cosa fa.** Riceve le risposte (in singolo o in batch), le persiste, attiva lo scoring per le
prove cognitive e la pipeline multicanale per la prova narrativa, persistendo i relativi esiti.

#### `backend/app/api/analysis.py`
**Scopo.** Analisi multicanale autonoma e consultazione dei risultati.
**Cosa fa.** Espone l'analisi di testo o audio (sincrona o in background) con persistenza,
gli endpoint per analizzare un campione *per un paziente* creando una sessione dedicata di sola
analisi, e gli endpoint di consultazione delle analisi salvate (elenco e dettaglio).

#### `backend/app/api/reports.py`
**Scopo.** Reportistica di sessione, longitudinale ed export.
**Cosa fa.** Espone la costruzione del report di sessione (integrando punteggi e analisi),
l'analisi longitudinale di un paziente e la generazione del PDF del report.

### 2.12 Test automatici

#### `backend/tests/test_scorers.py`
**Scopo.** Verifica dei moduli di scoring.
**Cosa fa.** Raccolta di test unitari (8) che validano il corretto calcolo dei punteggi delle
prove cognitive.

#### `backend/tests/test_schemas.py`
**Scopo.** Verifica degli schemi e delle relative validazioni.
**Cosa fa.** Test unitari (18) che verificano vincoli e regole di validazione degli schemi dei
test.

#### `backend/tests/test_analysis.py`
**Scopo.** Verifica della pipeline di analisi.
**Cosa fa.** Test unitari (11) sui canali di analisi e sul calcolo degli indicatori compositi.

#### `backend/tests/test_fase7.py`
**Scopo.** Verifica delle funzionalità di reportistica/longitudinale.
**Cosa fa.** Test unitari (9) relativi all'aggregazione del report e all'analisi dei trend.

### 2.13 Dipendenze e build del backend

#### `backend/Dockerfile`
**Scopo.** Immagine container del servizio backend.
**Cosa fa.** Definisce l'ambiente di esecuzione del backend (runtime Python, dipendenze,
comando di avvio) per l'esecuzione containerizzata.

#### `backend/requirements.txt` e `backend/requirements-analysis.txt`
**Scopo.** Elenco delle dipendenze Python.
**Cosa fa.** Il primo contiene le dipendenze principali del servizio; il secondo le librerie
dedicate alla pipeline di analisi (NLP, audio, modelli affettivi), separate per consentire
installazioni mirate.

#### `backend/pyproject.toml`
**Scopo.** Metadati e configurazione del progetto Python.
**Cosa fa.** Dichiara i metadati del pacchetto e la configurazione di strumenti di sviluppo.

#### `backend/demo_end_to_end.py`
**Scopo.** Dimostrazione del flusso completo senza LLM reale.
**Cosa fa.** Esegue end-to-end la generazione degli stimoli, una somministrazione simulata e la
produzione dei risultati, utile a verificare il funzionamento complessivo.

#### `backend/.env.example` (e `.env`)
**Scopo.** Modello delle variabili d'ambiente.
**Cosa fa.** Elenca le variabili di configurazione attese (database, provider LLM, credenziali,
storage). *Nota di sicurezza:* il file `.env` con valori reali non dovrebbe essere versionato.

#### File `__init__.py` (vari package del backend)
**Scopo.** Dichiarazione dei package Python.
**Cosa fa.** Rendono importabili le rispettive cartelle come moduli; non contengono logica
significativa.

---

## 3. Frontend

### 3.1 Avvio dell'applicazione

#### `frontend/index.html`
**Scopo.** Pagina HTML radice della Single Page Application.
**Cosa fa.** Fornisce il contenitore di montaggio dell'applicazione React e carica lo script di
ingresso.

#### `frontend/src/main.tsx`
**Scopo.** Punto di ingresso dell'applicazione React.
**Cosa fa.** Monta il componente radice `App` nel DOM e importa gli stili globali.

#### `frontend/src/App.tsx`
**Scopo.** Router principale dell'applicazione.
**Cosa fa.** Definisce le rotte: le pagine del clinico sono racchiuse nel `Layout` (con barra
laterale), mentre la rotta di esecuzione paziente (`/run/:sessionId`) è separata, in modo da
non esporre l'interfaccia del clinico.

### 3.2 Layout, design system e componenti UI

#### `frontend/src/components/Layout.tsx`
**Scopo.** Struttura della dashboard del clinico.
**Cosa fa.** Definisce la barra laterale di navigazione, l'intestazione con breadcrumb e l'area
dei contenuti in cui sono rese le pagine.

#### `frontend/src/components/ui/index.tsx`
**Scopo.** Libreria di componenti UI riutilizzabili.
**Cosa fa.** Fornisce componenti di base condivisi (`Card`, `Button`, `Badge`, `Icon`,
`EmptyState`) utilizzati in tutta l'applicazione per garantire coerenza visiva.

#### `frontend/src/styles/theme.ts`
**Scopo.** Token del design system.
**Cosa fa.** Definisce palette di colori, tipografia, raggi, ombre e spaziature, ispirati alla
reportistica clinica, per uno stile uniforme.

#### `frontend/src/styles/index.css`
**Scopo.** Stili globali dell'applicazione.
**Cosa fa.** Imposta reset, stili di base e regole globali del documento.

### 3.3 Pagine della dashboard

#### `frontend/src/components/HomePage.tsx`
**Scopo.** Panoramica iniziale.
**Cosa fa.** Mostra statistiche aggregate (numero di pazienti, sessioni per stato), le ultime
sessioni con accesso rapido al report e la distribuzione del rischio. Esporta anche il
componente `StatusBadge`.

#### `frontend/src/components/PatientsPage.tsx`
**Scopo.** Gestione dei pazienti.
**Cosa fa.** Elenca i pazienti, consente la ricerca e la creazione rapida tramite una finestra
modale.

#### `frontend/src/components/NewSessionPage.tsx`
**Scopo.** Creazione guidata di una sessione.
**Cosa fa.** Procedura a tre passi: scelta del paziente, selezione e configurazione delle prove,
generazione della sessione e produzione del link di esecuzione.

#### `frontend/src/components/SessionsPage.tsx`
**Scopo.** Elenco delle sessioni.
**Cosa fa.** Mostra le sessioni con stato e indicatori; per ciascuna propone l'accesso al report
quando sono presenti punteggi o analisi, altrimenti il link di esecuzione per il paziente.

#### `frontend/src/components/SessionReportPage.tsx`
**Scopo.** Visualizzazione del report di una sessione.
**Cosa fa.** Carica il report dal backend e lo mostra tramite `ReportDashboard`; recupera e
mostra inoltre il dettaglio completo delle analisi multicanale della sessione e gestisce
l'export in PDF.

#### `frontend/src/components/MultichannelPage.tsx`
**Scopo.** Analisi multicanale autonoma legata a un paziente.
**Cosa fa.** Richiede la scelta (o creazione) del paziente, esegue l'analisi di testo o audio
creando una sessione dedicata di sola analisi, mostra il risultato dettagliato e il link al
relativo report. Esporta il componente `AnalysisResultView`, riusato anche nel report.

#### `frontend/src/components/AnalysisHistory.tsx`
**Scopo.** Archivio delle analisi salvate.
**Cosa fa.** Elenca le analisi multicanale registrate con i tre indicatori e, su selezione, ne
mostra il dettaglio completo.

#### `frontend/src/components/LongitudinalPage.tsx`
**Scopo.** Analisi longitudinale di un paziente.
**Cosa fa.** Seleziona un paziente, carica i suoi report, li invia al backend per l'analisi dei
trend e ne visualizza l'esito tramite `LongitudinalChart`, mostrando la sequenza di sessioni
incluse.

#### `frontend/src/components/DoctorDashboard.tsx`
**Scopo.** Interfaccia operativa del clinico (variante integrata).
**Cosa fa.** Consente di creare/selezionare un paziente, configurare la batteria di prove e
avviare la valutazione.

### 3.4 Visualizzazioni

#### `frontend/src/components/ReportDashboard.tsx`
**Scopo.** Rappresentazione grafica del report di sessione.
**Cosa fa.** Mostra dati paziente, sintesi e rischio, i punteggi per test (nascosti quando non
vi sono prove cognitive), il radar dell'analisi multicanale, il dettaglio dei test e
osservazioni/raccomandazioni.

#### `frontend/src/components/LongitudinalChart.tsx`
**Scopo.** Rappresentazione grafica dei trend longitudinali.
**Cosa fa.** Visualizza l'andamento nel tempo delle metriche tracciate (cognitive e
multicanale), evidenzia la direzione del trend e gli alert clinici.

### 3.5 Esecuzione delle prove (lato paziente)

#### `frontend/src/components/SessionRunner.tsx`
**Scopo.** Orchestrazione dell'esecuzione di una sessione.
**Cosa fa.** Carica gli stimoli dal backend e instrada ogni prova al runner appropriato in
sequenza, raccogliendo le risposte e gestendo il passaggio tra le prove fino al termine.

#### `frontend/src/tests/CPTRunner.tsx`
**Scopo.** Somministrazione del Continuous Performance Test.
**Cosa fa.** Presenta gli stimoli a tempo e raccoglie le risposte del paziente con misurazione
precisa dei tempi.

#### `frontend/src/tests/DigitSpanRunner.tsx`
**Scopo.** Somministrazione del Digit Span.
**Cosa fa.** Riproduce le sequenze numeriche tramite sintesi vocale e registra la risposta
vocale del paziente per la successiva trascrizione/analisi.

#### `frontend/src/tests/StroopRunner.tsx`
**Scopo.** Somministrazione del test di Stroop.
**Cosa fa.** Mostra parole colorate e raccoglie la risposta del paziente sul colore
dell'inchiostro, misurando accuratezza e tempi.

#### `frontend/src/tests/GoNoGoRunner.tsx`
**Scopo.** Somministrazione del task Go/No-Go.
**Cosa fa.** Presenta stimoli colorati e raccoglie le risposte Go/No-Go in base alla regola
della fase corrente, misurando errori e tempi.

#### `frontend/src/tests/NarrativeRunner.tsx`
**Scopo.** Somministrazione della prova narrativa.
**Cosa fa.** Presenta lo spunto narrativo e raccoglie la risposta del paziente in forma
testuale o vocale, inviandola al backend per l'analisi multicanale.

### 3.6 Client API e utilità

#### `frontend/src/api/client.ts`
**Scopo.** Client HTTP verso il backend.
**Cosa fa.** Centralizza le chiamate all'API REST (pazienti, sessioni, stimoli, risposte,
report, analisi, longitudinale) e definisce i tipi dei dati scambiati.

#### `frontend/src/utils/timing.ts`
**Scopo.** Misurazione temporale ad alta precisione.
**Cosa fa.** Fornisce utilità basate su `performance.now()` per attese precise e per la
rilevazione del tempo di risposta nei test cognitivi.

### 3.7 Configurazione del frontend

#### `frontend/vite.config.ts`
**Scopo.** Configurazione del build tool (Vite).
**Cosa fa.** Configura il plugin React e i parametri di sviluppo/produzione.

#### `frontend/tsconfig.json`
**Scopo.** Configurazione del compilatore TypeScript.
**Cosa fa.** Definisce opzioni di compilazione e percorsi del progetto.

#### `frontend/package.json`
**Scopo.** Manifest del progetto frontend.
**Cosa fa.** Elenca dipendenze e script (`dev`, `build`, `preview`, `lint`).

---

## 4. Infrastruttura e script

#### `docker-compose.yml`
**Scopo.** Orchestrazione dei servizi locali.
**Cosa fa.** Definisce i servizi dell'ambiente: database PostgreSQL, storage MinIO, Redis,
backend e (opzionale) Ollama, con i relativi volumi persistenti.

#### `start.bat` / `start.ps1`
**Scopo.** Avvio dell'intero stack in locale.
**Cosa fa.** Avviano i servizi di supporto in Docker e i processi di backend (FastAPI) e
frontend (Vite). Due varianti equivalenti per prompt dei comandi e PowerShell.

#### `stop.ps1`
**Scopo.** Arresto dei servizi.
**Cosa fa.** Ferma i servizi avviati per l'ambiente di sviluppo.

#### `setup.ps1`
**Scopo.** Configurazione iniziale del progetto (una tantum).
**Cosa fa.** Predispone l'ambiente di sviluppo (dipendenze e prerequisiti).

#### `smoke_test.py`
**Scopo.** Verifica end-to-end via HTTP.
**Cosa fa.** Esegue un flusso completo (creazione paziente, sessione, invio di risposte,
generazione del report) per validare il funzionamento dell'API.

#### `README.md` e `LEGGIMI_SCRIPT.md`
**Scopo.** Documentazione introduttiva e guida agli script.
**Cosa fa.** Descrivono il progetto e le istruzioni d'uso degli script di avvio.

#### `docs/Fase1_Organizzazione_Informazioni.docx`, `docs/Fase2_Architettura_Sviluppo.docx`
**Scopo.** Documentazione di progetto delle fasi iniziali.
**Cosa fa.** Raccolgono l'organizzazione delle informazioni e le scelte architetturali maturate
nelle prime fasi di sviluppo.

#### `.gitignore`
**Scopo.** Esclusione di file dal versionamento.
**Cosa fa.** Indica gli artefatti da non versionare (ambienti, dipendenze, cache).

---

## 5. Note conclusive

La struttura del progetto realizza una separazione netta delle responsabilità: la generazione
degli stimoli, lo scoring delle prove e l'analisi multicanale sono moduli indipendenti, coordinati
dal livello API e resi persistenti nel database. La pipeline multicanale costituisce il
contributo metodologico centrale, con l'integrazione dei canali linguistico, prosodico e
affettivo in indicatori compositi, estesa al monitoraggio longitudinale.

*Raccomandazione operativa.* Si suggerisce di verificare che il file `backend/.env`, contenente
credenziali reali, non sia incluso nel versionamento pubblico, mantenendo nel repository il solo
`.env.example`.
