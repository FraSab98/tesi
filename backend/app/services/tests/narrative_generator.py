"""
Generator per il Narrative Task (quinto test).

Lo stimolo e una consegna verbale curata, scelta da un pool fisso per tipo
(NARRATIVE_PROMPT_POOL) per garantire standardizzazione e confrontabilita tra
sessioni. La generazione e quindi procedurale - come CPT e Go/No-Go
sovrascrive generate() e ignora l'LLM.

La "valutazione" di questo test NON e cronometrica: la risposta verbale del
paziente (audio o testo) viene instradata nella pipeline multi-canale
(MultiChannelAnalyzer) che produce gli indici cognitive_strain /
emotional_distress / communication_quality. L'aggregatore li integra poi nel
report a livello di sessione.
"""

import random
from typing import Type

from app.schemas.narrative import (
    NarrativeConfig,
    NarrativePrompt,
    NARRATIVE_PROMPT_POOL,
)
from app.services.tests.base import TestGenerator


class NarrativeGenerator(TestGenerator[NarrativeConfig, NarrativePrompt]):
    """Generator per il Narrative Task (produzione verbale spontanea)."""

    @property
    def test_name(self) -> str:
        return "Narrative"

    @property
    def category(self) -> str:
        return "F"  # allinea alla tua tassonomia Fase 1 (A-G)

    @property
    def output_schema(self) -> Type[NarrativePrompt]:
        return NarrativePrompt

    # I metodi di prompt restano implementati (sono astratti nella base) per
    # consentire, in futuro, una modalita LLM che generi varianti del prompt.
    # Oggi generate() e procedurale e non li usa.
    def build_system_prompt(self, config: NarrativeConfig) -> str:
        return (
            "Sei un generatore di consegne per un task di produzione verbale "
            "spontanea usato nella valutazione cognitiva. La consegna deve essere "
            "chiara, neutra, adatta a un paziente anziano, e non suggerire risposte. "
            "Restituisci SOLO il JSON conforme allo schema."
        )

    def build_user_prompt(self, config: NarrativeConfig) -> str:
        return (
            f"Genera una consegna di tipo '{config.prompt_type}' in lingua "
            f"'{config.language}', adatta a elicitare almeno {config.min_words} "
            f"parole di parlato spontaneo."
        )

    async def generate(self, config: NarrativeConfig) -> NarrativePrompt:
        """
        Override procedurale: seleziona una consegna dal pool curato.
        Standardizzazione clinica > varieta generativa.
        """
        pool = NARRATIVE_PROMPT_POOL.get(config.prompt_type)
        if not pool:
            raise ValueError(f"prompt_type sconosciuto: {config.prompt_type}")

        prompt_text = random.choice(pool)

        if config.response_mode in ("vocal", "both"):
            instructions = (
                "Rispondi parlando ad alta voce, con calma e prendendoti il tempo "
                f"che ti serve (almeno {config.min_response_seconds} secondi)."
            )
        else:
            instructions = "Scrivi la tua risposta liberamente, con i dettagli che vuoi."

        return NarrativePrompt(
            prompt_type=config.prompt_type,
            prompt_text=prompt_text,
            response_mode=config.response_mode,
            min_response_seconds=config.min_response_seconds,
            min_words=config.min_words,
            image_ref=config.image_ref,
            instructions=instructions,
        )
