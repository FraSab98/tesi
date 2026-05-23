"""
Schemi Pydantic per lo Stroop Color-Word Test.
Categoria di domanda: B — Stimolo con conflitto (interferenza)
Paper di riferimento: van Mourik et al., 1998
"""

from typing import List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

# Set colori supportati. Ogni colore ha word (italiana) e hex code
SUPPORTED_COLORS_IT = {
    "rosso": "#E53935",
    "verde": "#43A047",
    "blu": "#1E88E5",
    "giallo": "#FDD835",
}

SUPPORTED_COLORS_EN = {
    "red": "#E53935",
    "green": "#43A047",
    "blue": "#1E88E5",
    "yellow": "#FDD835",
}


class StroopStimulus(BaseModel):
    """Singolo stimolo Stroop: una parola-colore stampata in un colore."""
    word: str = Field(..., description="Parola che denota un colore")
    ink_color: str = Field(..., description="Colore in cui la parola è stampata")
    condition: Literal["congruent", "incongruent", "neutral"]

    @model_validator(mode="after")
    def validate_condition_consistency(self) -> "StroopStimulus":
        """word e ink_color devono essere coerenti con la condizione dichiarata."""
        w = self.word.lower()
        c = self.ink_color.lower()

        if self.condition == "congruent":
            if w != c:
                raise ValueError(
                    f"Condizione congruent ma word={w} != ink_color={c}"
                )
        elif self.condition == "incongruent":
            if w == c:
                raise ValueError(
                    f"Condizione incongruent ma word=ink_color={w}"
                )
        # neutral: la parola non è un colore (es. 'tavolo'), skip check

        return self


class StroopBlock(BaseModel):
    """Blocco di stimoli Stroop (es. 100 item da completare in 45 secondi)."""
    condition: Literal["word", "color", "color_word"]
    language: str = Field(default="it", min_length=2, max_length=5)
    stimuli: List[StroopStimulus] = Field(..., min_length=10, max_length=200)

    @model_validator(mode="after")
    def validate_stimuli_match_block_condition(self) -> "StroopBlock":
        """
        Condizione 'word'        -> tutti neutral (o congruenti banali)
        Condizione 'color'       -> parole neutre, ink_color = risposta richiesta
        Condizione 'color_word'  -> maggior parte incongruenti
        """
        if self.condition == "color_word":
            n_incongruent = sum(1 for s in self.stimuli if s.condition == "incongruent")
            ratio = n_incongruent / len(self.stimuli)
            if ratio < 0.7:
                raise ValueError(
                    f"Blocco color_word deve avere >=70% stimoli incongruenti, "
                    f"trovati {ratio:.0%}"
                )
        return self

    @model_validator(mode="after")
    def balanced_color_distribution(self) -> "StroopBlock":
        """Ogni colore usato deve apparire con frequenza simile (bilanciamento)."""
        from collections import Counter
        colors_used = Counter(s.ink_color.lower() for s in self.stimuli)
        if len(colors_used) < 2:
            return self
        max_count = max(colors_used.values())
        min_count = min(colors_used.values())
        if max_count > min_count * 2:
            raise ValueError(
                f"Distribuzione colori sbilanciata: {dict(colors_used)}"
            )
        return self


class StroopConfig(BaseModel):
    """Configurazione dello Stroop dal medico."""
    language: str = Field(default="it", min_length=2, max_length=5)
    colors: List[str] = Field(default=["rosso", "verde", "blu", "giallo"])
    conditions: List[Literal["word", "color", "color_word"]] = Field(
        default=["word", "color", "color_word"],
        description="Quali blocchi includere nel test"
    )
    items_per_block: int = Field(default=100, ge=20, le=200)
    block_duration_seconds: int = Field(default=45, ge=30, le=120)
    response_mode: Literal["vocal", "click"] = "click"
    congruent_ratio_in_cw: float = Field(
        default=0.0,
        ge=0.0,
        le=0.3,
        description="Quota di congruenti nel blocco color_word (default 0)"
    )

    @field_validator("colors")
    @classmethod
    def supported_colors(cls, v: List[str]) -> List[str]:
        if len(v) < 3 or len(v) > 6:
            raise ValueError("Numero colori deve essere tra 3 e 6")
        return [c.lower() for c in v]
