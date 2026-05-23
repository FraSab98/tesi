"""
Interfaccia astratta per provider LLM.
Permette di switchare tra Claude (API) e Llama (locale via Ollama)
senza modificare il codice dei generator.
"""

from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Interfaccia comune a tutti i provider LLM."""

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> T:
        """
        Genera output strutturato conforme allo schema Pydantic fornito.

        Args:
            system_prompt: istruzioni di sistema (ruolo, vincoli)
            user_prompt: richiesta specifica con parametri del test
            output_schema: classe Pydantic che l'output deve rispettare
            temperature: randomness (0=deterministico, 1=creativo)
            max_tokens: limite output

        Returns:
            Istanza validata dello schema

        Raises:
            GenerationFailedError: se dopo N retry l'output non è valido
        """
        ...

    @abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.5,
        max_tokens: int = 1000,
    ) -> str:
        """Generazione di testo libero (per prompt narrativi, feedback)."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome identificativo del provider (per logging e metadata)."""
        ...


class GenerationFailedError(Exception):
    """Sollevata quando l'LLM non riesce a produrre output valido dopo N retry."""

    def __init__(self, attempts: int, last_error: str):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Generazione fallita dopo {attempts} tentativi. Ultimo errore: {last_error}"
        )
