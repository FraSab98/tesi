#!/usr/bin/env python3
"""
Smoke test end-to-end della piattaforma di valutazione cognitiva.

Esegue l'intera catena contro il BACKEND IN ESECUZIONE:
  1. crea un paziente
  2. costruisce una sessione con i 5 test (CPT, DigitSpan, Stroop, GoNoGo, Narrative)
  3. scarica gli stimoli generati
  4. invia risposte finte ma realistiche per ogni test
  5. genera il report unificato (test + analisi multi-canale)

USO:
    # avvia prima il backend (uvicorn) con un .env valido, poi:
    pip install requests
    python smoke_test.py
    # opzionale: API_BASE=http://localhost:8000/api/v1 python smoke_test.py

NOTE:
  - Stroop e DigitSpan richiedono una ANTHROPIC_API_KEY valida nel .env
    (generano gli stimoli via LLM). CPT, GoNoGo e Narrative sono procedurali.
  - Se il build con 5 test fallisce con 422, probabilmente non hai aggiunto
    "Narrative" al Literal di TestConfigInSession in schemas/api.py: lo script
    te lo segnala e riprova con i soli 4 test MVP.
"""

import os
import sys
import time
import random

try:
    import requests
except ImportError:
    sys.exit("Manca 'requests'. Installa con: pip install requests")

API_BASE = os.getenv("API_BASE", "http://localhost:8000/api/v1")
CLINICIAN_ID = "dr_default"

# ----- config di default dei test (come nella UI) -----
DEFAULT_CONFIGS = {
    "CPT": {
        "target_letter": "X", "total_duration_minutes": 2, "target_ratio": 0.20,
        "stimulus_duration_ms": 250, "isi_min_ms": 1000, "isi_max_ms": 2000,
        "alphabet": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    },
    "DigitSpan": {
        "mode": "forward", "start_length": 3, "max_length": 6,
        "sequences_per_level": 2, "stop_after_failures": 2,
        "inter_digit_interval_ms": 1000, "tts_voice": "female", "tts_language": "it",
    },
    "Stroop": {
        "language": "it", "colors": ["rosso", "verde", "blu", "giallo"],
        "conditions": ["word", "color", "color_word"], "items_per_block": 10,
        "block_duration_seconds": 45, "response_mode": "click", "congruent_ratio_in_cw": 0.0,
    },
    "GoNoGo": {
        "go_color": "red", "nogo_color": "yellow", "include_formation": True,
        "include_reverse": True, "trials_per_phase": 20,
        "stimulus_duration_min_ms": 200, "stimulus_duration_max_ms": 1100,
        "isi_min_ms": 1300, "isi_max_ms": 7500, "response_feedback": False,
    },
    "Narrative": {
        "prompt_type": "perfect_day", "language": "it", "response_mode": "text",
        "min_response_seconds": 30, "min_words": 25, "image_ref": None,
        "run_multichannel": True,
    },
}

NARRATIVE_TEXT = (
    "La mia giornata perfetta inizierebbe con calma, senza fretta. "
    "Mi sveglierei tardi, prenderei un caffe lungo guardando fuori dalla finestra. "
    "Poi farei una passeggiata al parco, anche se a volte mi sento un po' stanco e confuso. "
    "Il pomeriggio leggerei un libro, ma faccio fatica a ricordare le cose. "
    "La sera vorrei stare con la famiglia, anche se ultimamente mi sento solo."
)


def _req(method, path, **kw):
    url = f"{API_BASE}{path}"
    r = requests.request(method, url, timeout=120, **kw)
    if not r.ok:
        print(f"  [HTTP {r.status_code}] {method} {path}\n  {r.text[:300]}")
    return r


def step(msg):
    print(f"\n{'='*60}\n{msg}\n{'='*60}")


# ----- costruttori di risposte finte per tipo di test -----

def build_responses(test_type, stimulus):
    """Genera risposte plausibili leggendo la struttura reale dello stimolo."""
    sid = stimulus["id"]
    data = stimulus["data"]
    out = []

    if test_type == "CPT":
        for i, s in enumerate(data.get("stimuli", [])):
            is_target = s.get("is_target", False)
            if is_target:
                responded = random.random() > 0.15           # ~15% omissioni
                rt = random.uniform(380, 820) if responded else None
            else:
                responded = random.random() < 0.06           # ~6% commissioni
                rt = random.uniform(300, 500) if responded else None
            out.append(_resp(sid, i, "key" if responded else "none",
                             reaction_time_ms=rt))

    elif test_type == "DigitSpan":
        for i, seq in enumerate(data.get("sequences", [])):
            target = seq.get("sequence", [])
            if len(target) <= 4:
                resp_seq = target                            # corretto sui corti
            else:
                resp_seq = target[:-1]                        # errore sui lunghi
            out.append(_resp(sid, i, "vocal",
                             response_value=" ".join(map(str, resp_seq))))

    elif test_type == "Stroop":
        for i, s in enumerate(data.get("stimuli", [])):
            correct = random.random() > (0.20 if s.get("condition") == "incongruent" else 0.05)
            color = s.get("ink_color") if correct else "errato"
            base = 1100 if s.get("condition") == "incongruent" else 650
            out.append(_resp(sid, i, "click", response_value=color,
                             reaction_time_ms=random.uniform(base, base + 300)))

    elif test_type == "GoNoGo":
        idx = 0
        for phase in data.get("phases", []):
            for trial in phase.get("trials", []):
                is_go = trial.get("stimulus_type") == "go"
                if is_go:
                    responded = random.random() > 0.05
                    rt = random.uniform(350, 600) if responded else None
                else:
                    responded = random.random() < 0.10        # qualche errore di inibizione
                    rt = random.uniform(300, 500) if responded else None
                out.append(_resp(sid, idx, "click" if responded else "none",
                                 reaction_time_ms=rt))
                idx += 1

    elif test_type == "Narrative":
        out.append(_resp(sid, 0, "key", response_value=NARRATIVE_TEXT))

    return out


def _resp(stimulus_id, trial_index, response_type, response_value=None, reaction_time_ms=None):
    return {
        "stimulus_id": stimulus_id,
        "session_id": SESSION_ID,
        "trial_index": trial_index,
        "response_type": response_type,
        "response_value": response_value,
        "reaction_time_ms": reaction_time_ms,
    }


# ============================================================
# MAIN
# ============================================================

SESSION_ID = None  # popolato dopo il build


def main():
    global SESSION_ID
    random.seed(42)

    print(f"Backend: {API_BASE}")

    # --- 1. Paziente ---
    step("1. Creo il paziente")
    code = f"SMOKE-{int(time.time())}"
    r = _req("POST", "/patients", json={
        "external_code": code, "age": 68, "language": "it",
        "clinical_suspicion": "MCI", "handedness": "right",
    })
    if not r.ok:
        sys.exit("Creazione paziente fallita. Backend avviato?")
    patient_id = r.json()["id"]
    print(f"  Paziente: {code} (id={patient_id[:8]})")

    # --- 2. Sessione con i 5 test ---
    step("2. Costruisco la sessione (5 test)")
    all_types = ["CPT", "DigitSpan", "Stroop", "GoNoGo", "Narrative"]
    tests = [{"test_type": t, "order": i, "config": DEFAULT_CONFIGS[t]}
             for i, t in enumerate(all_types)]

    r = _req("POST", "/sessions/build", json={
        "patient_id": patient_id, "clinician_id": CLINICIAN_ID, "tests": tests,
    })
    if r.status_code == 422:
        print("  ! Build con 5 test rifiutato (422).")
        print("  ! Probabile: 'Narrative' non aggiunto al Literal in schemas/api.py.")
        print("  ! Riprovo con i 4 test MVP cosi il resto della catena gira comunque...")
        tests = tests[:4]
        r = _req("POST", "/sessions/build", json={
            "patient_id": patient_id, "clinician_id": CLINICIAN_ID, "tests": tests,
        })
    if not r.ok:
        sys.exit("Build sessione fallito.")
    SESSION_ID = r.json()["id"]
    print(f"  Sessione: id={SESSION_ID[:8]}, test={[t['test_type'] for t in tests]}")

    # --- 3. Scarico gli stimoli ---
    step("3. Scarico gli stimoli generati")
    r = _req("GET", f"/sessions/{SESSION_ID}/stimuli")
    if not r.ok:
        sys.exit("Recupero stimoli fallito (gli stimoli LLM richiedono API key valida).")
    configs = r.json()
    for c in configs:
        print(f"  {c['test_type']}: {len(c['stimuli'])} stimolo/i")

    # --- 4. Invio risposte finte ---
    step("4. Invio risposte finte per ogni test")
    for c in configs:
        responses = []
        for stim in c["stimuli"]:
            responses.extend(build_responses(c["test_type"], stim))
        if not responses:
            print(f"  {c['test_type']}: nessuna risposta generata, salto")
            continue
        r = _req("POST", "/responses/batch", json={
            "session_id": SESSION_ID,
            "test_config_id": c["test_config_id"],
            "responses": responses,
        })
        if r.ok:
            body = r.json()
            extra = body.get("score") or ("analisi multicanale" if body.get("analyses") else "")
            print(f"  {c['test_type']}: {len(responses)} risposte inviate "
                  f"-> {('score' if body.get('score') else 'multicanale') if extra else 'ok'}")

    # --- 5. Report unificato ---
    step("5. Genero il report unificato")
    r = _req("GET", f"/reports/session/{SESSION_ID}")
    if not r.ok:
        sys.exit("Generazione report fallita.")
    rep = r.json()

    print(f"\n  RISCHIO: {rep.get('overall_risk_level', '?').upper()}  "
          f"| score complessivo: {rep.get('overall_cognitive_score', '?')}")
    print("\n  RACCOMANDAZIONI:")
    for rec in rep.get("recommendations", []):
        print(f"   - {rec}")
    print("\n  FLAG (con descrizione):")
    found = False
    for t in rep.get("test_scores", []):
        for f in t.get("flags", []):
            found = True
            if isinstance(f, dict):
                print(f"   [{t['test_type']}] (sev {f.get('severity')}) {f.get('description')}")
            else:
                print(f"   [{t['test_type']}] {f}  <-- ancora codice: aggiorna aggregator.py")
    if not found:
        print("   (nessun flag)")
    mc = rep.get("multichannel")
    if mc:
        print(f"\n  MULTICANALE: strain={mc.get('avg_cognitive_strain')}, "
              f"distress={mc.get('avg_emotional_distress')}, "
              f"quality={mc.get('avg_communication_quality')}, "
              f"audio/testo analizzati={mc.get('n_audio_responses')}")

    step("SMOKE TEST COMPLETATO")
    print(f"  Apri il report nel browser: /sessions/{SESSION_ID}/report")
    print(f"  PDF: GET {API_BASE}/reports/session/{SESSION_ID}/pdf")


if __name__ == "__main__":
    main()
