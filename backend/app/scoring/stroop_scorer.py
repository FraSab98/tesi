"""
Scoring per Stroop Color-Word Test.

Implementa i due metodi standard di calcolo dell'interference score
(van Mourik et al., 1998):
- Metodo classico (Hammes): C - CW
- Metodo Golden: CW - (W*C / (W+C))
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np


@dataclass
class StroopResponse:
    """Risposta del paziente a un singolo stimolo Stroop."""
    stimulus_index: int
    word: str
    ink_color: str
    condition: str  # congruent, incongruent, neutral
    response_color: Optional[str]  # colore nominato/cliccato
    reaction_time_ms: Optional[float]
    correct: bool


@dataclass
class StroopBlockScore:
    """Punteggio di un blocco Stroop."""
    block_type: str  # 'word', 'color', 'color_word'
    n_items: int
    n_correct: int
    accuracy: float
    mean_rt_ms: float
    sd_rt_ms: float


@dataclass
class StroopScore:
    """Punteggio completo Stroop."""
    block_scores: Dict[str, StroopBlockScore]
    # Interference scores (solo se abbiamo W, C, CW)
    interference_classic: Optional[float]  # C - CW
    interference_golden: Optional[float]   # CW - (W*C / (W+C))
    interference_rt: Optional[float]       # mean_RT_CW - mean_RT_C

    def to_dict(self) -> dict:
        return {
            "blocks": {
                name: {
                    "n_items": s.n_items,
                    "n_correct": s.n_correct,
                    "accuracy": round(s.accuracy, 4),
                    "mean_rt_ms": round(s.mean_rt_ms, 2),
                    "sd_rt_ms": round(s.sd_rt_ms, 2),
                }
                for name, s in self.block_scores.items()
            },
            "interference_classic": (
                round(self.interference_classic, 2)
                if self.interference_classic is not None else None
            ),
            "interference_golden": (
                round(self.interference_golden, 2)
                if self.interference_golden is not None else None
            ),
            "interference_rt_ms": (
                round(self.interference_rt, 2)
                if self.interference_rt is not None else None
            ),
        }


def _score_single_block(
    responses: List[StroopResponse],
    block_type: str,
) -> StroopBlockScore:
    """Calcola il punteggio di un singolo blocco."""
    n = len(responses)
    n_correct = sum(1 for r in responses if r.correct)
    accuracy = n_correct / n if n else 0.0

    rts = [r.reaction_time_ms for r in responses if r.reaction_time_ms is not None and r.correct]
    mean_rt = float(np.mean(rts)) if rts else 0.0
    sd_rt = float(np.std(rts)) if len(rts) > 1 else 0.0

    return StroopBlockScore(
        block_type=block_type,
        n_items=n,
        n_correct=n_correct,
        accuracy=accuracy,
        mean_rt_ms=mean_rt,
        sd_rt_ms=sd_rt,
    )


def score_stroop(
    word_block: Optional[List[StroopResponse]] = None,
    color_block: Optional[List[StroopResponse]] = None,
    color_word_block: Optional[List[StroopResponse]] = None,
) -> StroopScore:
    """
    Calcola il punteggio complessivo Stroop.
    Accetta i blocchi opzionalmente: se solo CW è presente, ritorna solo
    accuratezza e RT senza interference score.
    """
    block_scores = {}

    if word_block:
        block_scores["word"] = _score_single_block(word_block, "word")
    if color_block:
        block_scores["color"] = _score_single_block(color_block, "color")
    if color_word_block:
        block_scores["color_word"] = _score_single_block(color_word_block, "color_word")

    interference_classic = None
    interference_golden = None
    interference_rt = None

    # Interference score richiede C e CW
    if "color" in block_scores and "color_word" in block_scores:
        c_score = block_scores["color"].n_correct
        cw_score = block_scores["color_word"].n_correct

        # Metodo classico
        interference_classic = c_score - cw_score

        # Interference RT (sempre calcolabile con C e CW)
        interference_rt = (
            block_scores["color_word"].mean_rt_ms
            - block_scores["color"].mean_rt_ms
        )

        # Metodo Golden richiede anche W
        if "word" in block_scores:
            w = block_scores["word"].n_correct
            c = c_score
            cw = cw_score
            if (w + c) > 0:
                predicted_cw = (w * c) / (w + c)
                interference_golden = cw - predicted_cw

    return StroopScore(
        block_scores=block_scores,
        interference_classic=interference_classic,
        interference_golden=interference_golden,
        interference_rt=interference_rt,
    )
