"""
Classe base astratta per tutti i generator di test.

Definisce il contratto comune che ogni generator (CPT, Digit Span, Stroop,
Go/No-Go e i futuri test della Fase 1) deve rispettare, e fornisce la logica
di generazione condivisa basata su LLM.

Pattern: Template Method.
    Il metodo concreto `generate()` fissa lo scheletro dell'algoritmo
    (costruisci prompt -> chiama LLM -> ottieni output validato), mentre i
    "passi variabili" (quale prompt, quale schema, quale temperatura) sono
    delegati ai metodi astratti che le sottoclassi implementano.

    I generator i cui stimoli sono puramente algoritmici (CPT, Go/No-Go)
    semplicemente sovrascrivono `generate()` con la loro generazione
    procedurale, ignorando il percorso LLM.

Generics:
    ConfigT — schema Pydantic della configurazione in ingresso (es. StroopConfig)
    OutputT — schema Pydantic degli stimoli prodotti (es. StroopBlock)
"""

import logging
from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar

from pydantic import BaseModel

from app.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

ConfigT = TypeVar("ConfigT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class TestGenerator(ABC, Generic[ConfigT, OutputT]):
    """
    Base astratta per i generator di stimoli.

    Una sottoclasse deve:
      1. dichiarare i metadati identificativi: `test_name`, `category`,
         `output_schema`;
      2. implementare la costruzione del prompt: `build_system_prompt()` e
         `build_user_prompt()`.

    Opzionalmente può:
      - sovrascrivere `default_temperature()` / `max_tokens()` per regolare
        gli iperparametri di generazione;
      - sovrascrivere `generate()` quando la generazione è procedurale e non
        passa per l'LLM (vedi CPTGenerator e GoNoGoGenerator).
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        Args:
            llm_provider: provider LLM (Claude o Ollama) usato dalla
                implementazione di default di `generate()`. I generator
                procedurali lo ricevono comunque per uniformità di interfaccia,
                anche se possono non usarlo.
        """
        self.llm_provider = llm_provider

    # ------------------------------------------------------------------
    # Metadati identificativi (obbligatori)
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def test_name(self) -> str:
        """Nome del test (per logging e metadata), es. 'Stroop_color_word'."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Categoria di domanda della Fase 1 (A–G)."""
        ...

    @property
    @abstractmethod
    def output_schema(self) -> Type[OutputT]:
        """Schema Pydantic che l'output generato deve rispettare."""
        ...

    # ------------------------------------------------------------------
    # Costruzione del prompt (obbligatori)
    # ------------------------------------------------------------------
    @abstractmethod
    def build_system_prompt(self, config: ConfigT) -> str:
        """Istruzioni di sistema: ruolo, vincoli, formato dell'output."""
        ...

    @abstractmethod
    def build_user_prompt(self, config: ConfigT) -> str:
        """Richiesta specifica con i parametri della configurazione."""
        ...

    # ------------------------------------------------------------------
    # Iperparametri (hook con default sovrascrivibili)
    # ------------------------------------------------------------------
    def default_temperature(self) -> float:
        """Temperatura di default; abbassarla per test a vincoli stretti."""
        return 0.3

    def max_tokens(self) -> int:
        """Limite di token in output per la generazione."""
        return 2000

    # ------------------------------------------------------------------
    # Template Method: scheletro condiviso della generazione via LLM
    # ------------------------------------------------------------------
    async def generate(self, config: ConfigT) -> OutputT:
        """
        Genera gli stimoli del test.

        Implementazione di default basata su LLM: costruisce i prompt,
        invoca `generate_structured` del provider (che gestisce internamente
        validazione Pydantic e retry con feedback) e restituisce l'istanza
        validata dello `output_schema`.

        Le sottoclassi procedurali sovrascrivono questo metodo.

        Raises:
            GenerationFailedError: propagato dal provider se l'output non è
                valido dopo i retry previsti.
        """
        system_prompt = self.build_system_prompt(config)
        user_prompt = self.build_user_prompt(config)

        logger.info(
            "[%s] Generazione via %s (cat. %s, temp=%.2f)",
            self.test_name,
            self.llm_provider.provider_name,
            self.category,
            self.default_temperature(),
        )

        return await self.llm_provider.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=self.output_schema,
            temperature=self.default_temperature(),
            max_tokens=self.max_tokens(),
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} test={self.test_name!r} category={self.category!r}>"
