"""
Scoring per Continuous Performance Test.

Basato su Advokat et al. (2007) e metriche standard del CPT:
- Errori di omissione (target mancato)
- Errori di commissione (risposta a non-target)
- Tempo di reazione medio
- Variabilità del tempo di reazione (indicatore chiave di attenzione)
- Instabilità attentiva combinata (variabilità RT + tasso di omissioni)
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class CPTResponse:
    """Risposta del paziente a un singolo stimolo CPT."""
    stimulus_index: int
    stimulus: str
    is_target: bool
    responded: bool  # True se il paziente ha premuto il tasto
    reaction_time_ms: Optional[float]  # None se non ha risposto


@dataclass
class CPTScore:
    """Punteggio finale di un CPT."""
    n_stimuli: int
    n_targets: int
    n_omissions: int           # target mancati
    n_commissions: int         # falsi positivi
    omission_rate: float       # % omissioni
    commission_rate: float     # % commissioni
    mean_rt_ms: float          # RT medio sui target corretti
    sd_rt_ms: float            # deviazione standard RT
    rt_variability: float      # coefficiente di variazione RT
    attention_instability: float  # variabilita RT + lapsus attentivi
    attention_score: float     # score composito 0-100

    def to_dict(self) -> dict:
        return {
            "n_stimuli": self.n_stimuli,
            "n_targets": self.n_targets,
            "n_omissions": self.n_omissions,
            "n_commissions": self.n_commissions,
            "omission_rate": round(self.omission_rate, 4),
            "commission_rate": round(self.commission_rate, 4),
            "mean_rt_ms": round(self.mean_rt_ms, 2),
            "sd_rt_ms": round(self.sd_rt_ms, 2),
            "rt_variability": round(self.rt_variability, 4),
            "attention_instability": round(self.attention_instability, 4),
            "attention_score": round(self.attention_score, 2),
        }


def score_cpt(responses: List[CPTResponse]) -> CPTScore:
    """
    Calcola il punteggio di un CPT.

    Args:
        responses: lista delle risposte del paziente a ciascuno stimolo

    Returns:
        CPTScore con tutte le metriche
    """
    if not responses:
        raise ValueError("Nessuna risposta da valutare")

    targets = [r for r in responses if r.is_target]
    non_targets = [r for r in responses if not r.is_target]

    n_targets = len(targets)

    # Omissioni: target non risposti
    omissions = [r for r in targets if not r.responded]
    n_omissions = len(omissions)

    # Commissioni: non-target a cui si e risposto
    commissions = [r for r in non_targets if r.responded]
    n_commissions = len(commissions)

    # RT dei soli target colpiti correttamente
    correct_target_rts = [
        r.reaction_time_ms for r in targets
        if r.responded and r.reaction_time_ms is not None
    ]

    # Tutti i RT validi (target colpiti + commissioni): variabilita piu sensibile
    all_response_rts = [
        r.reaction_time_ms for r in responses
        if r.responded and r.reaction_time_ms is not None
    ]

    # Tassi di errore (definiti PRIMA di usarli)
    omission_rate = n_omissions / n_targets if n_targets > 0 else 0.0
    commission_rate = n_commissions / len(non_targets) if non_targets else 0.0

    # RT medi e deviazioni
    mean_rt = float(np.mean(correct_target_rts)) if correct_target_rts else 0.0
    sd_rt = float(np.std(correct_target_rts)) if len(correct_target_rts) > 1 else 0.0

    mean_rt_all = float(np.mean(all_response_rts)) if all_response_rts else 0.0
    sd_rt_all = float(np.std(all_response_rts)) if len(all_response_rts) > 1 else 0.0
    rt_variability = sd_rt_all / mean_rt_all if mean_rt_all > 0 else 0.0

    # "Instabilita attentiva" combinata: variabilita RT + tasso di lapsus.
    # Ora omission_rate e gia definito.
    attention_instability = rt_variability + (omission_rate * 0.5)

    # Score composito: 100 - penalita
    # Pesi da letteratura: omissione piu grave di commissione per attenzione sostenuta
    attention_score = 100.0
    attention_score -= omission_rate * 60      # peso pieno sulle omissioni
    attention_score -= commission_rate * 30
    attention_score -= min(rt_variability * 60, 25)
    attention_score = max(0, attention_score)

    return CPTScore(
        n_stimuli=len(responses),
        n_targets=n_targets,
        n_omissions=n_omissions,
        n_commissions=n_commissions,
        omission_rate=omission_rate,
        commission_rate=commission_rate,
        mean_rt_ms=mean_rt,
        sd_rt_ms=sd_rt,
        rt_variability=rt_variability,
        attention_instability=attention_instability,
        attention_score=attention_score,
    )
