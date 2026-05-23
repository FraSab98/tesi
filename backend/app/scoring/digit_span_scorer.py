"""
Scoring per Digit Span Test.

Implementa l'approccio innovativo di Asgari et al. (2020): oltre al punteggio
convenzionale (risposta corretta/errata), estrae metriche di correttezza fine
basate sulla distanza di Levenshtein tra risposta e target.

Queste metriche sono più sensibili al declino cognitivo precoce (MCI) rispetto
al punteggio binario tradizionale.
"""

from dataclasses import dataclass
from typing import List
import numpy as np


@dataclass
class DigitSpanResponse:
    """Risposta del paziente a una singola sequenza."""
    target_sequence: List[int]
    response_sequence: List[int]  # da trascrizione Whisper
    length: int


@dataclass
class DigitSpanItemMetrics:
    """Metriche a livello di singolo item (Paper 5)."""
    n_correct: int        # cifre giuste al posto giusto
    n_deleted: int        # cifre omesse
    n_inserted: int       # cifre aggiunte
    n_substituted: int    # cifre sostituite
    edit_distance: int    # Levenshtein totale
    is_exact: bool        # True se risposta perfetta


@dataclass
class DigitSpanScore:
    """Punteggio completo Digit Span."""
    mode: str
    n_items: int
    n_exact: int                      # conteggio convenzionale
    longest_correct: int              # più lunga sequenza corretta
    # Metriche innovative da Paper 5
    mean_edit_distance: float
    std_edit_distance: float
    total_correct_words: int
    total_deleted: int
    total_inserted: int
    total_substituted: int
    # Score compositi
    conventional_score: float         # 0-100 basato su n_exact
    fine_grained_score: float         # 0-100 basato su edit distances

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "n_items": self.n_items,
            "n_exact": self.n_exact,
            "longest_correct": self.longest_correct,
            "mean_edit_distance": round(self.mean_edit_distance, 3),
            "std_edit_distance": round(self.std_edit_distance, 3),
            "total_correct_words": self.total_correct_words,
            "total_deleted": self.total_deleted,
            "total_inserted": self.total_inserted,
            "total_substituted": self.total_substituted,
            "conventional_score": round(self.conventional_score, 2),
            "fine_grained_score": round(self.fine_grained_score, 2),
        }


def _levenshtein_operations(target: List[int], response: List[int]) -> DigitSpanItemMetrics:
    """
    Calcola le operazioni di edit tra target e response.
    Implementazione diretta (no dipendenze esterne) per trasparenza nella tesi.
    """
    m, n = len(target), len(response)

    # Matrice di DP
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if target[i - 1] == response[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # deletion
                    dp[i][j - 1],      # insertion
                    dp[i - 1][j - 1],  # substitution
                )

    # Backtrack per contare tipi di operazioni
    i, j = m, n
    deletions = insertions = substitutions = 0

    while i > 0 or j > 0:
        if i > 0 and j > 0 and target[i - 1] == response[j - 1]:
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            substitutions += 1
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            deletions += 1
            i -= 1
        else:
            insertions += 1
            j -= 1

    edit_distance = dp[m][n]
    # Parole "corrette": cifre del target che compaiono alla posizione giusta
    n_correct = sum(1 for k in range(min(m, n)) if target[k] == response[k])

    return DigitSpanItemMetrics(
        n_correct=n_correct,
        n_deleted=deletions,
        n_inserted=insertions,
        n_substituted=substitutions,
        edit_distance=edit_distance,
        is_exact=(target == response),
    )


def score_digit_span(
    responses: List[DigitSpanResponse],
    mode: str,
) -> DigitSpanScore:
    """
    Calcola il punteggio di un Digit Span sia con approccio tradizionale
    sia con quello innovativo di Asgari et al. (2020).
    """
    if not responses:
        raise ValueError("Nessuna risposta da valutare")

    item_metrics = [
        _levenshtein_operations(r.target_sequence, r.response_sequence)
        for r in responses
    ]

    n_exact = sum(1 for m in item_metrics if m.is_exact)

    # Più lunga sequenza ripetuta esattamente
    longest_correct = 0
    for r, m in zip(responses, item_metrics):
        if m.is_exact and r.length > longest_correct:
            longest_correct = r.length

    edit_distances = [m.edit_distance for m in item_metrics]
    mean_ed = float(np.mean(edit_distances))
    std_ed = float(np.std(edit_distances)) if len(edit_distances) > 1 else 0.0

    total_correct = sum(m.n_correct for m in item_metrics)
    total_deleted = sum(m.n_deleted for m in item_metrics)
    total_inserted = sum(m.n_inserted for m in item_metrics)
    total_substituted = sum(m.n_substituted for m in item_metrics)

    n_items = len(responses)

    # Score convenzionale: % di risposte esatte
    conventional = (n_exact / n_items) * 100 if n_items else 0.0

    # Score fine-grained: 100 - penalità basata su edit distance normalizzata
    total_target_length = sum(len(r.target_sequence) for r in responses)
    if total_target_length > 0:
        total_ed = sum(edit_distances)
        error_rate = total_ed / total_target_length
        fine_grained = max(0.0, 100.0 * (1 - error_rate))
    else:
        fine_grained = 0.0

    return DigitSpanScore(
        mode=mode,
        n_items=n_items,
        n_exact=n_exact,
        longest_correct=longest_correct,
        mean_edit_distance=mean_ed,
        std_edit_distance=std_ed,
        total_correct_words=total_correct,
        total_deleted=total_deleted,
        total_inserted=total_inserted,
        total_substituted=total_substituted,
        conventional_score=conventional,
        fine_grained_score=fine_grained,
    )
