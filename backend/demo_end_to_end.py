"""
Demo end-to-end della piattaforma (senza LLM reale).

Mostra il flusso completo: generazione stimoli -> somministrazione simulata
-> scoring. I generator CPT e Go/No-Go sono procedurali, quindi non
richiedono API key per essere testati.

Esecuzione:
    cd backend/
    python demo_end_to_end.py
"""

import asyncio
import json
import random
from typing import List

from app.schemas.cpt import CPTConfig
from app.schemas.go_nogo import GoNoGoConfig
from app.services.tests.cpt_generator import CPTGenerator
from app.services.tests.go_nogo_generator import GoNoGoGenerator
from app.scoring.cpt_scorer import score_cpt, CPTResponse
from app.scoring.go_nogo_scorer import score_go_nogo, GoNoGoResponse


# ==================== MOCK LLM (non serve per CPT/GoNoGo) ====================

class MockLLMProvider:
    """Finto provider per testare generator procedurali."""
    @property
    def provider_name(self):
        return "mock:none"

    async def generate_structured(self, *args, **kwargs):
        raise NotImplementedError("Mock: non supporta LLM reale")

    async def generate_text(self, *args, **kwargs):
        return ""


# ==================== SIMULAZIONE RISPOSTE PAZIENTE ====================

def simulate_patient_cpt_responses(sequence, patient_profile="healthy"):
    """Simula le risposte di un paziente al CPT.

    patient_profile:
    - 'healthy': risposte rapide, pochi errori
    - 'mci': RT più lenti, più errori di omissione
    - 'adhd': RT variabili, più errori di commissione
    """
    responses = []
    for i, stim in enumerate(sequence.stimuli):
        if patient_profile == "healthy":
            # 95% dei target risposti correttamente, RT 400-500ms
            if stim.is_target:
                responded = random.random() < 0.95
                rt = random.gauss(450, 50) if responded else None
            else:
                responded = random.random() < 0.02  # 2% commissioni
                rt = random.gauss(420, 60) if responded else None
        elif patient_profile == "mci":
            # 70% dei target risposti, RT 600-700ms, alta variabilità
            if stim.is_target:
                responded = random.random() < 0.70
                rt = random.gauss(680, 180) if responded else None
            else:
                responded = random.random() < 0.08
                rt = random.gauss(650, 200) if responded else None
        elif patient_profile == "adhd":
            # RT molto variabili, più commissioni
            if stim.is_target:
                responded = random.random() < 0.88
                rt = random.gauss(500, 200) if responded else None
            else:
                responded = random.random() < 0.15  # molte commissioni
                rt = random.gauss(380, 120) if responded else None

        responses.append(CPTResponse(
            stimulus_index=i,
            stimulus=stim.stimulus,
            is_target=stim.is_target,
            responded=responded,
            reaction_time_ms=max(150, rt) if rt else None,
        ))
    return responses


def simulate_patient_go_nogo_responses(test, patient_profile="healthy"):
    """Simula risposte al Go/No-Go."""
    responses = []
    global_idx = 0
    for phase in test.phases:
        for trial in phase.trials:
            if patient_profile == "healthy":
                if trial.stimulus_type == "go":
                    responded = random.random() < 0.97
                    rt = random.gauss(400, 60) if responded else None
                else:
                    responded = random.random() < 0.05
                    rt = random.gauss(400, 80) if responded else None
            else:  # mci
                if trial.stimulus_type == "go":
                    responded = random.random() < 0.75
                    rt = random.gauss(650, 180) if responded else None
                else:
                    responded = random.random() < 0.20
                    rt = random.gauss(550, 150) if responded else None

            responses.append(GoNoGoResponse(
                trial_index=global_idx,
                phase=phase.phase,
                stimulus_type=trial.stimulus_type,
                responded=responded,
                reaction_time_ms=max(150, rt) if rt else None,
            ))
            global_idx += 1
    return responses


# ==================== DEMO ====================

async def run_cpt_demo():
    print("\n" + "=" * 70)
    print("DEMO 1: Continuous Performance Test")
    print("=" * 70)

    config = CPTConfig(
        target_letter="X",
        total_duration_minutes=5,
        target_ratio=0.20,
    )
    generator = CPTGenerator(MockLLMProvider())

    print(f"\n[1/3] Generazione sequenza CPT...")
    print(f"      Durata: {config.total_duration_minutes} min")
    print(f"      Target ratio: {config.target_ratio:.0%}")

    sequence = await generator.generate(config)
    n_targets = sum(1 for s in sequence.stimuli if s.is_target)
    print(f"      ✓ Generati {len(sequence.stimuli)} stimoli ({n_targets} target)")

    # Simula 3 profili di paziente
    for profile in ["healthy", "mci", "adhd"]:
        print(f"\n[2/3] Simulazione paziente profilo '{profile}'...")
        random.seed(42)
        responses = simulate_patient_cpt_responses(sequence, profile)

        print(f"[3/3] Scoring...")
        score = score_cpt(responses)
        print(f"      Omissioni: {score.n_omissions}/{score.n_targets} ({score.omission_rate:.1%})")
        print(f"      Commissioni: {score.n_commissions}")
        print(f"      RT medio: {score.mean_rt_ms:.0f} ms")
        print(f"      RT variabilità: {score.rt_variability:.3f}")
        print(f"      >>> Attention Score: {score.attention_score:.1f}/100 <<<")


async def run_go_nogo_demo():
    print("\n" + "=" * 70)
    print("DEMO 2: Go/No-Go Task")
    print("=" * 70)

    config = GoNoGoConfig(
        go_color="#43A047",
        nogo_color="#E53935",
        include_formation=True,
        include_reverse=True,
        trials_per_phase=20,
    )
    generator = GoNoGoGenerator(MockLLMProvider())

    print(f"\n[1/3] Generazione test Go/No-Go...")
    test = await generator.generate(config)
    n_trials = sum(len(p.trials) for p in test.phases)
    print(f"      ✓ Generate {len(test.phases)} fasi, {n_trials} trial totali")
    for phase in test.phases:
        n_go = sum(1 for t in phase.trials if t.stimulus_type == "go")
        print(f"        - {phase.phase}: {len(phase.trials)} trial ({n_go} Go)")

    for profile in ["healthy", "mci"]:
        print(f"\n[2/3] Simulazione paziente '{profile}'...")
        random.seed(42)
        responses = simulate_patient_go_nogo_responses(test, profile)

        print(f"[3/3] Scoring (Watanabe 2024)...")
        score = score_go_nogo(responses)
        print(f"      Miss totali: {score.total_miss}")
        print(f"      Mistake totali: {score.total_mistake}")
        print(f"      Errore totale: {score.total_error}")
        print(f"      Accuracy: {score.overall_accuracy:.1%}")
        print(f"      >>> Screening Risk: {score.screening_risk_score:.1f}/100 <<<")
        if score.total_error <= 2:
            print(f"      Indicazione: coerente con cognitivamente sano (cut-off MoCA)")
        elif score.total_error <= 6:
            print(f"      Indicazione: possibile MCI (supera cut-off MoCA=2)")
        else:
            print(f"      Indicazione: alto rischio (supera cut-off MMSE=6)")


async def run_full_demo():
    print("\n" + "█" * 70)
    print("  PIATTAFORMA DI VALUTAZIONE COGNITIVA — DEMO END-TO-END")
    print("  Tesi Magistrale — Fase 2 MVP")
    print("█" * 70)

    await run_cpt_demo()
    await run_go_nogo_demo()

    print("\n" + "=" * 70)
    print("  Demo completata ✓")
    print("=" * 70)
    print("""
Prossimi passi:
  1. Configurare ANTHROPIC_API_KEY in .env per attivare generator LLM
     (Digit Span e Stroop richiedono l'LLM)
  2. Avviare Docker Compose: docker compose up -d
  3. Avviare backend: cd backend && uvicorn app.main:app --reload
  4. Avviare frontend: cd frontend && npm run dev
  5. Aprire http://localhost:5173
""")


if __name__ == "__main__":
    asyncio.run(run_full_demo())
