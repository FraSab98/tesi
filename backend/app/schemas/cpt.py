"""
Schemi Pydantic per il Continuous Performance Test (CPT).
Categoria di domanda: A — Stimolo reattivo semplice
Paper di riferimento: Advokat et al., 2007

Questi schemi validano l'output dell'LLM: se il JSON generato non rispetta
i vincoli, il servizio di generazione richiama automaticamente l'LLM con
un messaggio di errore fino a 3 volte.
"""

from typing import List
from pydantic import BaseModel, Field, field_validator, model_validator


class CPTStimulus(BaseModel):
    """Singolo stimolo del CPT: una lettera con metadata temporale."""
    stimulus: str = Field(
        ...,
        min_length=1,
        max_length=1,
        description="Singola lettera maiuscola (A-Z)"
    )
    is_target: bool = Field(
        ...,
        description="True se questo stimolo richiede risposta (o astensione, a seconda della variante)"
    )
    isi_ms: int = Field(
        ...,
        ge=500,
        le=5000,
        description="Intervallo inter-stimolo in millisecondi"
    )

    @field_validator("stimulus")
    @classmethod
    def uppercase_letter(cls, v: str) -> str:
        if not v.isalpha():
            raise ValueError("stimulus must be an alphabetic character")
        return v.upper()


class CPTSequence(BaseModel):
    """
    Sequenza completa di stimoli per un blocco CPT.
    Input che l'LLM deve produrre.
    """
    target_letter: str = Field(
        ...,
        min_length=1,
        max_length=1,
        description="Lettera target (default: 'X')"
    )
    stimuli: List[CPTStimulus] = Field(
        ...,
        min_length=10,
        description="Sequenza ordinata di stimoli"
    )

    @model_validator(mode="after")
    def validate_sequence_constraints(self) -> "CPTSequence":
        # Vincolo 1: non più di 3 target consecutivi
        consecutive_targets = 0
        for s in self.stimuli:
            if s.is_target:
                consecutive_targets += 1
                if consecutive_targets > 3:
                    raise ValueError(
                        "Non possono esserci più di 3 target consecutivi "
                        "(bias di sequenza)"
                    )
            else:
                consecutive_targets = 0

        # Vincolo 2: ratio target ragionevole (5-50%)
        n_targets = sum(1 for s in self.stimuli if s.is_target)
        ratio = n_targets / len(self.stimuli)
        if ratio < 0.05 or ratio > 0.5:
            raise ValueError(
                f"Ratio target {ratio:.2%} fuori dal range accettabile [5%, 50%]"
            )

        # Vincolo 3: tutti i target hanno stimulus == target_letter
        for i, s in enumerate(self.stimuli):
            if s.is_target and s.stimulus != self.target_letter.upper():
                raise ValueError(
                    f"Stimolo {i} marcato come target ma non corrisponde a target_letter"
                )
            if not s.is_target and s.stimulus == self.target_letter.upper():
                raise ValueError(
                    f"Stimolo {i} è la target_letter ma non è marcato come target"
                )

        return self


class CPTConfig(BaseModel):
    """Parametri di configurazione che il medico invia al sistema."""
    target_letter: str = Field(default="X", min_length=1, max_length=1)
    total_duration_minutes: int = Field(default=14, ge=5, le=30)
    target_ratio: float = Field(default=0.10, ge=0.05, le=0.5)
    stimulus_duration_ms: int = Field(default=250, ge=100, le=1000)
    isi_min_ms: int = Field(default=1000, ge=500, le=5000)
    isi_max_ms: int = Field(default=4000, ge=500, le=5000)
    alphabet: str = Field(
        default="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        description="Lettere usabili come distrattori"
    )

    @model_validator(mode="after")
    def validate_isi_range(self) -> "CPTConfig":
        if self.isi_min_ms >= self.isi_max_ms:
            raise ValueError("isi_min_ms deve essere < isi_max_ms")
        return self

    def total_stimuli_count(self) -> int:
        """Calcola quanti stimoli servono per coprire la durata."""
        avg_isi = (self.isi_min_ms + self.isi_max_ms) / 2
        total_ms_per_stimulus = self.stimulus_duration_ms + avg_isi
        total_ms = self.total_duration_minutes * 60 * 1000
        return int(total_ms / total_ms_per_stimulus)
