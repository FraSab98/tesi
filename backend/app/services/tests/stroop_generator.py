"""
Generator per Stroop Color-Word Test.

L'LLM è utile qui per generare liste bilanciate con varietà di coppie
parola-colore, rispettando il vincolo che in condizione incongruente
la parola non deve mai corrispondere al colore dell'inchiostro.
"""

import random
from typing import Type, List

from app.schemas.stroop import (
    StroopConfig,
    StroopBlock,
    StroopStimulus,
    SUPPORTED_COLORS_IT,
    SUPPORTED_COLORS_EN,
)
from app.services.tests.base import TestGenerator


class StroopGenerator(TestGenerator[StroopConfig, StroopBlock]):
    """Generator per Stroop Test.

    Nota: genera UN blocco alla volta. Il servizio chiamante genera
    separatamente il blocco word, color e color_word.
    """

    def __init__(self, llm_provider, block_condition: str = "color_word"):
        super().__init__(llm_provider)
        self.block_condition = block_condition

    @property
    def test_name(self) -> str:
        return f"Stroop_{self.block_condition}"

    @property
    def category(self) -> str:
        return "B"

    @property
    def output_schema(self) -> Type[StroopBlock]:
        return StroopBlock

    def default_temperature(self) -> float:
        return 0.3

    def build_system_prompt(self, config: StroopConfig) -> str:
        return (
            "Sei un generatore di stimoli per lo Stroop Color-Word Test. "
            "Generi liste bilanciate di coppie parola-colore rispettando "
            "rigorosamente il tipo di condizione richiesta. "
            "Restituisci SOLO il JSON."
        )

    def build_user_prompt(self, config: StroopConfig) -> str:
        colors = config.colors
        n = config.items_per_block

        if self.block_condition == "color_word":
            return self._incongruent_prompt(colors, n, config.language)
        elif self.block_condition == "word":
            return self._word_reading_prompt(colors, n, config.language)
        elif self.block_condition == "color":
            return self._color_naming_prompt(colors, n, config.language)
        else:
            raise ValueError(f"Condizione non supportata: {self.block_condition}")

    def _incongruent_prompt(self, colors: List[str], n: int, lang: str) -> str:
        return (
            f"Genera un blocco di {n} stimoli per la condizione INCONGRUENTE "
            f"dello Stroop in lingua {lang}.\n\n"
            f"Colori disponibili: {', '.join(colors)}\n\n"
            f"Regole:\n"
            f"1. Ogni stimolo: una parola-colore stampata in un colore DIVERSO "
            f"(mai word == ink_color)\n"
            f"2. condition deve essere 'incongruent' per ogni stimolo\n"
            f"3. Distribuzione bilanciata: ogni colore deve apparire circa {n // len(colors)} volte "
            f"come ink_color\n"
            f"4. Varietà nelle coppie: non usare sempre le stesse combinazioni\n"
            f"5. Evitare più di 2 stimoli consecutivi con lo stesso ink_color\n\n"
            f'Esempio: {{"condition":"color_word","language":"{lang}","stimuli":['
            f'{{"word":"rosso","ink_color":"blu","condition":"incongruent"}},'
            f'{{"word":"verde","ink_color":"giallo","condition":"incongruent"}},'
            f'{{"word":"blu","ink_color":"verde","condition":"incongruent"}}]}}'
        )

    def _word_reading_prompt(self, colors: List[str], n: int, lang: str) -> str:
        return (
            f"Genera un blocco di {n} stimoli per la condizione LETTURA PAROLE "
            f"dello Stroop in lingua {lang}.\n\n"
            f"In questa condizione le parole-colore sono stampate in NERO "
            f"(ink_color='black') e il paziente le legge ad alta voce.\n\n"
            f"Regole:\n"
            f"1. Ogni stimolo ha ink_color='black'\n"
            f"2. word è una delle parole-colore: {', '.join(colors)}\n"
            f"3. condition='neutral' (la parola non è in conflitto con il colore)\n"
            f"4. Distribuzione bilanciata delle parole\n\n"
            f"Esempio: stimulus = {{\"word\":\"rosso\",\"ink_color\":\"black\",\"condition\":\"neutral\"}}"
        )

    def _color_naming_prompt(self, colors: List[str], n: int, lang: str) -> str:
        return (
            f"Genera un blocco di {n} stimoli per la condizione DENOMINAZIONE COLORI "
            f"dello Stroop in lingua {lang}.\n\n"
            f"In questa condizione il paziente vede stringhe di 'X' colorate "
            f"(non parole) e deve nominare il colore.\n\n"
            f"Regole:\n"
            f"1. word è sempre 'XXXX' (o simbolo neutro)\n"
            f"2. ink_color è uno dei colori: {', '.join(colors)}\n"
            f"3. condition='neutral'\n"
            f"4. Distribuzione bilanciata dei colori\n\n"
            f"Esempio: stimulus = {{\"word\":\"XXXX\",\"ink_color\":\"rosso\",\"condition\":\"neutral\"}}"
        )
