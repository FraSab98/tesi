"""
Scoring per Go/No-Go Task.

Basato su Watanabe et al. (2024):
- Miss: mancata risposta a stimolo Go
- Mistake: risposta a stimolo No-Go (errore di commissione)
- Total error = miss + mistake
- Mean reaction time sui Go corretti
- Il paper mostra forte correlazione con MMSE e MoCA
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
import numpy as np


@dataclass
class GoNoGoResponse:
    """Risposta a un trial Go/No-Go."""
    trial_index: int
    phase: str
    stimulus_type: str  # 'go' o 'nogo'
    responded: bool
    reaction_time_ms: Optional[float]


@dataclass
class GoNoGoPhaseScore:
    """Punteggio di una singola fase."""
    phase: str
    n_trials: int
    n_go: int
    n_nogo: int
    n_miss: int            # Go non risposti
    n_mistake: int         # NoGo a cui ha risposto
    miss_rate: float
    mistake_rate: float
    mean_rt_go_ms: float   # RT medio su Go corretti
    sd_rt_go_ms: float


@dataclass
class GoNoGoScore:
    """Punteggio completo Go/No-Go."""
    phases: Dict[str, GoNoGoPhaseScore]
    total_miss: int
    total_mistake: int
    total_error: int
    overall_accuracy: float
    # Metriche chiave Paper 9
    screening_risk_score: float  # 0-100, più alto = più a rischio

    def to_dict(self) -> dict:
        return {
            "phases": {
                name: {
                    "n_trials": ps.n_trials,
                    "n_miss": ps.n_miss,
                    "n_mistake": ps.n_mistake,
                    "miss_rate": round(ps.miss_rate, 4),
                    "mistake_rate": round(ps.mistake_rate, 4),
                    "mean_rt_go_ms": round(ps.mean_rt_go_ms, 2),
                    "sd_rt_go_ms": round(ps.sd_rt_go_ms, 2),
                }
                for name, ps in self.phases.items()
            },
            "total_miss": self.total_miss,
            "total_mistake": self.total_mistake,
            "total_error": self.total_error,
            "overall_accuracy": round(self.overall_accuracy, 4),
            "screening_risk_score": round(self.screening_risk_score, 2),
        }


def _score_phase(responses: List[GoNoGoResponse], phase: str) -> GoNoGoPhaseScore:
    """Calcola le metriche di una singola fase."""
    go_trials = [r for r in responses if r.stimulus_type == "go"]
    nogo_trials = [r for r in responses if r.stimulus_type == "nogo"]

    n_miss = sum(1 for r in go_trials if not r.responded)
    n_mistake = sum(1 for r in nogo_trials if r.responded)

    miss_rate = n_miss / len(go_trials) if go_trials else 0.0
    mistake_rate = n_mistake / len(nogo_trials) if nogo_trials else 0.0

    # RT sui Go correttamente risposti
    correct_go_rts = [
        r.reaction_time_ms for r in go_trials
        if r.responded and r.reaction_time_ms is not None
    ]
    mean_rt = float(np.mean(correct_go_rts)) if correct_go_rts else 0.0
    sd_rt = float(np.std(correct_go_rts)) if len(correct_go_rts) > 1 else 0.0

    return GoNoGoPhaseScore(
        phase=phase,
        n_trials=len(responses),
        n_go=len(go_trials),
        n_nogo=len(nogo_trials),
        n_miss=n_miss,
        n_mistake=n_mistake,
        miss_rate=miss_rate,
        mistake_rate=mistake_rate,
        mean_rt_go_ms=mean_rt,
        sd_rt_go_ms=sd_rt,
    )


def score_go_nogo(responses: List[GoNoGoResponse]) -> GoNoGoScore:
    """
    Calcola il punteggio completo del Go/No-Go.

    Il paper Watanabe (2024) trova che:
    - cut-off di 2 errori totali correlando con MoCA <25 (sensibilità 94%)
    - cut-off di 6 errori totali correlando con MMSE <27 (sensibilità 75%)
    """
    # Raggruppa per fase
    by_phase = {}
    for r in responses:
        by_phase.setdefault(r.phase, []).append(r)

    phase_scores = {
        phase: _score_phase(resp, phase)
        for phase, resp in by_phase.items()
    }

    total_miss = sum(ps.n_miss for ps in phase_scores.values())
    total_mistake = sum(ps.n_mistake for ps in phase_scores.values())
    total_error = total_miss + total_mistake

    total_trials = len(responses)
    overall_accuracy = 1 - (total_error / total_trials) if total_trials else 0.0

    # Risk score: scala 0-100 basata sui cut-off del paper
    # 0 errori -> rischio 0; 2 errori -> rischio ~50 (soglia MoCA); 6+ errori -> rischio 100
    if total_error == 0:
        risk = 0.0
    elif total_error <= 2:
        risk = 25 + (total_error * 12.5)
    elif total_error <= 6:
        risk = 50 + ((total_error - 2) * 10)
    else:
        risk = min(100.0, 90 + (total_error - 6) * 2)

    return GoNoGoScore(
        phases=phase_scores,
        total_miss=total_miss,
        total_mistake=total_mistake,
        total_error=total_error,
        overall_accuracy=overall_accuracy,
        screening_risk_score=risk,
    )
