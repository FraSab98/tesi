"""
Schemi Pydantic per il Narrative Task (quinto test).
Categoria di domanda: F - Produzione verbale spontanea
Paper di riferimento: paradigma "Cookie Theft" (Boston Diagnostic Aphasia Exam),
ADReSS/ADReSSo Challenge (Luz et al., 2020/2021).

A differenza dei 4 test timing/accuracy, questo task NON ha uno score
cronometrico: la sua valutazione e l'analisi multi-canale (linguistica +
prosodia + sentiment/emotion) sulla risposta verbale del paziente.

NOTA sulla categoria: 'F' e un segnaposto, allinealo alla tua tassonomia
Fase 1 (A-G) come hai fatto per CPT='A' e DigitSpan='C'.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


# Prompt curati per tipo. Tenuti fissi per garantire confrontabilita tra
# sessioni (standardizzazione clinica). Piu varianti equivalenti per tipo,
# cosi il paziente non memorizza lo stimolo se ripete il test nel tempo.
NARRATIVE_PROMPT_POOL: dict[str, list[str]] = {
    "picture_description": [
        "Osserva l'immagine e descrivimi tutto quello che vedi accadere, "
        "con piu dettagli possibile.",
        "Guarda con attenzione la scena e raccontami cosa sta succedendo, "
        "chi sono le persone e cosa stanno facendo.",
    ],
    "perfect_day": [
        "Raccontami com'e fatta la tua giornata perfetta, dal mattino alla sera.",
        "Descrivimi nel dettaglio come trascorreresti una giornata ideale, "
        "se potessi scegliere tu ogni cosa.",
    ],
    "daily_routine": [
        "Raccontami cosa fai di solito in una giornata tipica, dal risveglio "
        "fino a quando vai a dormire.",
        "Descrivimi le tue abitudini in un giorno normale, passo dopo passo.",
    ],
    "story_retell": [
        "Ti racconto una breve storia; poi ti chiedero di ripetermela con "
        "parole tue, ricordando piu particolari che puoi.",
        "Ascolta questo breve racconto e poi prova a raccontarmelo di nuovo, "
        "cercando di non tralasciare i dettagli.",
    ],
}


class NarrativeConfig(BaseModel):
    """Configurazione del Narrative Task scelta dal medico."""
    prompt_type: Literal[
        "picture_description", "perfect_day", "daily_routine", "story_retell"
    ] = "perfect_day"
    language: str = Field(default="it", min_length=2, max_length=5)
    response_mode: Literal["vocal", "text", "both"] = "vocal"
    min_response_seconds: int = Field(
        default=30, ge=10, le=300,
        description="Durata minima attesa della risposta vocale (guida, non blocco)"
    )
    min_words: int = Field(
        default=25, ge=5, le=500,
        description="Numero minimo di parole atteso (guida per l'analisi linguistica)"
    )
    image_ref: Optional[str] = Field(
        default=None,
        description="ID/URL dell'immagine, obbligatorio per picture_description"
    )
    # Attiva esplicitamente la pipeline multi-canale su questa risposta
    run_multichannel: bool = True

    @model_validator(mode="after")
    def image_required_for_picture(self) -> "NarrativeConfig":
        if self.prompt_type == "picture_description" and not self.image_ref:
            raise ValueError(
                "picture_description richiede 'image_ref' (l'immagine da descrivere)"
            )
        return self


class NarrativePrompt(BaseModel):
    """
    Stimolo prodotto dal generator: la consegna mostrata/letta al paziente.
    E' l'equivalente di CPTSequence/DigitSpanBatch per gli altri test.
    """
    prompt_type: str
    prompt_text: str = Field(..., min_length=10)
    response_mode: str
    min_response_seconds: int = Field(..., ge=10, le=300)
    min_words: int = Field(..., ge=5, le=500)
    image_ref: Optional[str] = None
    instructions: str = Field(
        default="Rispondi liberamente, prenditi il tempo che ti serve.",
        description="Istruzioni operative per il paziente"
    )
