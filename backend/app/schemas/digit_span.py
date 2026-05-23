"""
Schemi Pydantic per il Digit Span Test.
Categoria di domanda: C — Sequenza da memorizzare e ripetere
Paper di riferimento: Asgari et al., 2020

Forward Digit Span (FDS): ripetizione in ordine diretto
Backward Digit Span (BDS): ripetizione in ordine inverso
"""

from typing import List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class DigitSpanSequence(BaseModel):
    """Singola sequenza numerica da far ripetere al paziente."""
    sequence: List[int] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Sequenza di cifre da 1 a 9"
    )
    length: int = Field(..., ge=2, le=10)

    @field_validator("sequence")
    @classmethod
    def digits_in_range(cls, v: List[int]) -> List[int]:
        for d in v:
            if d < 1 or d > 9:
                raise ValueError(f"Cifra {d} fuori dal range [1,9]")
        return v

    @model_validator(mode="after")
    def limit_digit_repetitions(self) -> "DigitSpanSequence":
        """Per sequenze brevi (<= 5), nessuna cifra deve apparire più di una volta.
        Per sequenze lunghe, massimo 2 occorrenze della stessa cifra.
        Riduce gli appigli mnemonici che faciliterebbero artificialmente il compito."""
        from collections import Counter
        counts = Counter(self.sequence)
        max_allowed = 1 if self.length <= 5 else 2
        for digit, count in counts.items():
           if count > max_allowed:
               raise ValueError(
                   f"Cifra {digit} ripetuta {count} volte in sequenza di lunghezza "
                   f"{self.length} (max consentito: {max_allowed})"
               )
        return self

    @model_validator(mode="after")
    def length_matches_sequence(self) -> "DigitSpanSequence":
        if len(self.sequence) != self.length:
            raise ValueError(
                f"length={self.length} ma sequence ha {len(self.sequence)} elementi"
            )
        return self

    @model_validator(mode="after")
    def no_trivial_patterns(self) -> "DigitSpanSequence":
        seq = self.sequence
        # Vincolo 1: mai 2+ cifre identiche consecutive
        for i in range(len(seq) - 1):
            if seq[i] == seq[i + 1]:
                raise ValueError(
                    f"Cifre identiche consecutive alla posizione {i}: {seq}"
                )

        # Vincolo 2: no progressioni aritmetiche di lunghezza >= 3
        if len(seq) >= 3:
            for i in range(len(seq) - 2):
                diff1 = seq[i + 1] - seq[i]
                diff2 = seq[i + 2] - seq[i + 1]
                if diff1 == diff2 and abs(diff1) == 1:
                    raise ValueError(
                        f"Progressione aritmetica banale trovata: {seq[i:i+3]}"
                    )

        return self


class DigitSpanBatch(BaseModel):
    """
    Output atteso dall'LLM: un batch di sequenze per un livello di difficoltà.
    Tipicamente 2 sequenze per livello (come nel paper Asgari 2020).
    """
    mode: Literal["forward", "backward"]
    sequences: List[DigitSpanSequence] = Field(..., min_length=1, max_length=10)

    @model_validator(mode="after")
    def sequences_same_length(self) -> "DigitSpanBatch":
        """Tutte le sequenze del batch devono avere la stessa lunghezza."""
        lengths = {len(s.sequence) for s in self.sequences}
        if len(lengths) > 1:
            raise ValueError(
                f"Sequenze nel batch hanno lunghezze diverse: {lengths}"
            )
        return self

    @model_validator(mode="after")
    def balanced_digit_distribution(self) -> "DigitSpanBatch":
        """
        Le cifre 1-9 dovrebbero apparire in modo ragionevolmente bilanciato
        nel batch. Nessuna cifra dovrebbe dominare.
        """
        from collections import Counter
        all_digits = [d for s in self.sequences for d in s.sequence]
        if len(all_digits) < 10:
            return self  # troppo poche per valutare

        counts = Counter(all_digits)
        max_count = max(counts.values())
        min_count = min(counts.values()) if len(counts) == 9 else 0
        avg = len(all_digits) / 9

        # Nessuna cifra può apparire più di 3x la media
        if max_count > avg * 3:
            raise ValueError(
                f"Distribuzione cifre non bilanciata: {dict(counts)}"
            )
        return self


class DigitSpanConfig(BaseModel):
    """Configurazione di un test Digit Span dal medico."""
    mode: Literal["forward", "backward"] = "forward"
    start_length: int = Field(default=3, ge=2, le=5)
    max_length: int = Field(default=8, ge=4, le=10)
    sequences_per_level: int = Field(default=2, ge=1, le=4)
    stop_after_failures: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Interruzione dopo N fallimenti consecutivi allo stesso livello"
    )
    inter_digit_interval_ms: int = Field(default=1000, ge=500, le=2000)
    tts_voice: Literal["male", "female"] = "female"
    tts_language: str = Field(default="it", min_length=2, max_length=5)

    @model_validator(mode="after")
    def validate_length_range(self) -> "DigitSpanConfig":
        if self.start_length >= self.max_length:
            raise ValueError("start_length deve essere < max_length")
        # Backward è più difficile: default max più basso
        if self.mode == "backward" and self.max_length > 7:
            raise ValueError(
                "Per modalità backward, max_length consigliato <= 7"
            )
        return self
