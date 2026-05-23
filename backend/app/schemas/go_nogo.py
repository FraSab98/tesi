"""
Schemi Pydantic per il Go/No-Go Task.
Categoria di domanda: A — Stimolo reattivo semplice (con inibizione)
Paper di riferimento: Watanabe et al., 2024

Fasi del test:
- Formation: 5 prove di addestramento (solo stimoli Go)
- Differentiation: 20 prove (10 Go + 10 No-Go)
- Reverse Differentiation: 20 prove con regole invertite
"""

from typing import List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class GoNoGoTrial(BaseModel):
    """Singolo trial del Go/No-Go."""
    stimulus_type: Literal["go", "nogo"]
    stimulus_color: str = Field(..., description="Colore/identificativo dello stimolo")
    stimulus_duration_ms: int = Field(..., ge=200, le=1100)
    isi_ms: int = Field(..., ge=1300, le=7500)


class GoNoGoPhase(BaseModel):
    """Una fase del test Go/No-Go."""
    phase: Literal["formation", "differentiation", "reverse_differentiation"]
    go_stimulus_color: str = Field(..., description="Colore dello stimolo Go in questa fase")
    nogo_stimulus_color: str = Field(..., description="Colore dello stimolo NoGo in questa fase")
    trials: List[GoNoGoTrial] = Field(...)

    @model_validator(mode="after")
    def validate_trial_counts(self) -> "GoNoGoPhase":
        n = len(self.trials)
        if self.phase == "formation":
            if n < 5 or n > 10:
                raise ValueError(f"Formation richiede 5-10 trial, trovati {n}")
            # In formation solo go
            if any(t.stimulus_type == "nogo" for t in self.trials):
                raise ValueError("Formation deve contenere solo stimoli Go")
        else:
            if n < 15 or n > 30:
                raise ValueError(f"Differentiation richiede 15-30 trial, trovati {n}")
            # Deve essere bilanciato
            n_go = sum(1 for t in self.trials if t.stimulus_type == "go")
            ratio = n_go / n
            if ratio < 0.4 or ratio > 0.6:
                raise ValueError(
                    f"Bilanciamento Go/NoGo fuori range: {ratio:.0%} Go"
                )

        return self

    @model_validator(mode="after")
    def validate_colors_match_type(self) -> "GoNoGoPhase":
        """Ogni trial deve avere il colore corretto per il suo tipo."""
        for i, t in enumerate(self.trials):
            expected_color = (
                self.go_stimulus_color if t.stimulus_type == "go"
                else self.nogo_stimulus_color
            )
            if t.stimulus_color != expected_color:
                raise ValueError(
                    f"Trial {i}: tipo={t.stimulus_type} ma colore={t.stimulus_color}, "
                    f"atteso {expected_color}"
                )
        return self

    @model_validator(mode="after")
    def no_long_runs_same_type(self) -> "GoNoGoPhase":
        """Evita sequenze di stesso tipo più lunghe di 3.
        Non si applica alla formation (che è per definizione tutta Go)."""
        if self.phase == "formation":
            return self
        run = 1
        for i in range(1, len(self.trials)):
            if self.trials[i].stimulus_type == self.trials[i - 1].stimulus_type:
                run += 1
                if run > 3:
                    raise ValueError(
                        f"Più di 3 trial dello stesso tipo consecutivi "
                        f"alla posizione {i}"
                    )
            else:
                run = 1
        return self

    @model_validator(mode="after")
    def reverse_phase_has_swapped_colors(self) -> "GoNoGoPhase":
        """In reverse_differentiation, go_color e nogo_color devono essere swappati
        rispetto a differentiation. Questo check è solo informativo a livello di
        singola fase; il check completo è nel wrapper GoNoGoTest."""
        return self


class GoNoGoTest(BaseModel):
    """Test completo Go/No-Go: insieme delle fasi."""
    phases: List[GoNoGoPhase] = Field(..., min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_phase_sequence(self) -> "GoNoGoTest":
        """Le fasi devono seguire l'ordine corretto."""
        expected_order = ["formation", "differentiation", "reverse_differentiation"]
        phase_names = [p.phase for p in self.phases]

        # Devono essere un prefisso di expected_order
        for i, name in enumerate(phase_names):
            if name != expected_order[i]:
                raise ValueError(
                    f"Ordine fasi errato: atteso {expected_order[:len(phase_names)]}, "
                    f"trovato {phase_names}"
                )
        return self

    @model_validator(mode="after")
    def reverse_phase_colors_swapped(self) -> "GoNoGoTest":
        """In reverse_differentiation i colori Go/NoGo devono essere invertiti
        rispetto alla differentiation."""
        if len(self.phases) < 3:
            return self

        diff = next((p for p in self.phases if p.phase == "differentiation"), None)
        rev = next((p for p in self.phases if p.phase == "reverse_differentiation"), None)

        if diff and rev:
            if (diff.go_stimulus_color != rev.nogo_stimulus_color
                    or diff.nogo_stimulus_color != rev.go_stimulus_color):
                raise ValueError(
                    "Reverse phase deve avere i colori Go/NoGo invertiti "
                    "rispetto alla differentiation phase"
                )
        return self


class GoNoGoConfig(BaseModel):
    """Configurazione Go/No-Go dal medico."""
    go_color: str = Field(default="red", description="Colore stimolo Go")
    nogo_color: str = Field(default="yellow", description="Colore stimolo NoGo")
    include_formation: bool = True
    include_reverse: bool = True
    trials_per_phase: int = Field(default=20, ge=15, le=30)
    stimulus_duration_min_ms: int = Field(default=200, ge=200, le=500)
    stimulus_duration_max_ms: int = Field(default=1100, ge=500, le=1500)
    isi_min_ms: int = Field(default=1300, ge=1000, le=3000)
    isi_max_ms: int = Field(default=7500, ge=3000, le=10000)
    response_feedback: bool = Field(
        default=False,
        description="Se True, feedback immediato errore/corretto al paziente"
    )

    @model_validator(mode="after")
    def validate_colors_distinct(self) -> "GoNoGoConfig":
        if self.go_color == self.nogo_color:
            raise ValueError("go_color e nogo_color devono essere diversi")
        return self

    @model_validator(mode="after")
    def validate_timing_ranges(self) -> "GoNoGoConfig":
        if self.stimulus_duration_min_ms >= self.stimulus_duration_max_ms:
            raise ValueError("stimulus_duration min deve essere < max")
        if self.isi_min_ms >= self.isi_max_ms:
            raise ValueError("isi min deve essere < max")
        return self
