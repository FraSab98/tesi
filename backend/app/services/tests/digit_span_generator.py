"""
Generator per Digit Span Test.

Qui l'LLM è davvero utile: evita pattern banali (progressioni, ripetizioni),
bilancia la distribuzione delle cifre, e può applicare regole linguistiche
(evitare sequenze fonologicamente simili in certe lingue).
"""

from typing import Type

from app.schemas.digit_span import DigitSpanConfig, DigitSpanBatch
from app.services.tests.base import TestGenerator


class DigitSpanGenerator(TestGenerator[DigitSpanConfig, DigitSpanBatch]):
    """Generator per Digit Span Test (forward e backward)."""

    @property
    def test_name(self) -> str:
        return "DigitSpan"

    @property
    def category(self) -> str:
        return "C"

    @property
    def output_schema(self) -> Type[DigitSpanBatch]:
        return DigitSpanBatch

    def default_temperature(self) -> float:
        return 0.4  # serve un po' di varietà per evitare pattern ripetitivi

    def build_system_prompt(self, config: DigitSpanConfig) -> str:
        return (
            "Sei un generatore di sequenze numeriche per il Digit Span Test, "
            "uno strumento validato per valutare memoria di lavoro e attenzione verbale. "
            "Le sequenze devono rispettare rigorosi criteri psicometrici: "
            "assenza di pattern prevedibili, distribuzione bilanciata delle cifre, "
            "nessuna struttura mnemonica aiutante (no date, no progressioni). "
            "Restituisci SOLO il JSON, senza commenti."
        )

    def build_user_prompt(self, config: DigitSpanConfig) -> str:
        mode_it = "diretto (forward)" if config.mode == "forward" else "inverso (backward)"
        difficulty_note = ""
        if config.mode == "backward":
            difficulty_note = (
                "\nNOTA: essendo backward, il paziente dovrà invertire mentalmente "
                "la sequenza, quindi la difficoltà è maggiore a parità di lunghezza."
            )

        return (
            f"Genera un batch di sequenze numeriche per un Digit Span {mode_it}.\n"
            f"{difficulty_note}\n\n"
            f"Parametri:\n"
            f"- mode: '{config.mode}'\n"
            f"- numero sequenze: {config.sequences_per_level}\n"
            f"- lunghezza di ciascuna: {config.start_length}\n\n"
            f"Vincoli OBBLIGATORI:\n"
            f"1. Cifre da 1 a 9 (MAI lo zero)\n"
            f"2. MAI due cifre identiche consecutive (es. 3,3 vietato)\n"
            f"3. MAI progressioni aritmetiche di lunghezza >= 3 con passo 1 "
            f"(es. 4,5,6 vietato; 4,5,7 ok)\n"
            f"4. Distribuzione bilanciata: ogni cifra deve apparire con frequenza simile "
            f"nel batch\n"
            f"5. Evitare sequenze che corrispondono a date note, numeri telefonici, "
            f"pattern culturali italiani\n\n"
            f"Esempi di output corretto:\n"
            f'- mode=forward, length=4, n=2: {{"mode":"forward","sequences":['
            f'{{"sequence":[3,8,1,5],"length":4}},'
            f'{{"sequence":[7,2,9,4],"length":4}}]}}\n'
            f'- mode=backward, length=3, n=2: {{"mode":"backward","sequences":['
            f'{{"sequence":[5,2,8],"length":3}},'
            f'{{"sequence":[9,4,6],"length":3}}]}}\n\n'
            f"Genera {config.sequences_per_level} sequenze di lunghezza {config.start_length} "
            f"per la modalità {config.mode}."
        )
