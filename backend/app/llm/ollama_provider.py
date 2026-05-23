"""
Implementazione del LLMProvider che usa Ollama per modelli locali
(Llama 3.1, Mistral, etc.).

Richiede Ollama installato e in esecuzione:
    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull llama3.1:8b
"""

import json
import logging
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError

try:
    import httpx
except ImportError:
    httpx = None

from .provider import LLMProvider, GenerationFailedError

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OllamaProvider(LLMProvider):
    """Provider che usa modelli locali via Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        max_retries: int = 3,
        timeout: float = 120.0,
    ):
        if httpx is None:
            raise ImportError("Installare con `pip install httpx` per usare OllamaProvider")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return f"ollama:{self.model}"

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> T:
        """
        Llama locale non ha native tool use come Claude. Strategia:
        1. Aggiungi lo schema JSON nel prompt
        2. Richiedi output JSON puro
        3. Usa il format='json' di Ollama che forza JSON valido
        4. Valida con Pydantic + retry
        """
        schema_str = json.dumps(output_schema.model_json_schema(), indent=2)

        augmented_system = (
            f"{system_prompt}\n\n"
            f"IMPORTANTE: Devi rispondere SOLO con JSON valido conforme a questo schema:\n"
            f"{schema_str}\n\n"
            f"Non aggiungere spiegazioni, preamboli o commenti. SOLO il JSON."
        )

        current_prompt = user_prompt
        last_error = ""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": augmented_system},
                                {"role": "user", "content": current_prompt},
                            ],
                            "format": "json",  # forza output JSON
                            "stream": False,
                            "options": {
                                "temperature": temperature,
                                "num_predict": max_tokens,
                            },
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    raw_json = data["message"]["content"]

                    # Parse e valida
                    parsed = json.loads(raw_json)
                    validated = output_schema.model_validate(parsed)

                    logger.info(
                        f"[{self.provider_name}] Generazione riuscita al tentativo {attempt+1}"
                    )
                    return validated

                except (ValidationError, json.JSONDecodeError) as e:
                    last_error = str(e)
                    logger.warning(
                        f"[{self.provider_name}] Tentativo {attempt+1} fallito: {last_error[:200]}"
                    )
                    current_prompt = (
                        f"{user_prompt}\n\n"
                        f"ATTENZIONE: Il tuo output precedente era malformato:\n"
                        f"{last_error}\n\n"
                        f"Rispondi con JSON VALIDO conforme allo schema. Solo JSON, niente altro."
                    )
                except Exception as e:
                    last_error = f"{type(e).__name__}: {e}"
                    logger.error(
                        f"[{self.provider_name}] Errore al tentativo {attempt+1}: {last_error}"
                    )

        raise GenerationFailedError(self.max_retries, last_error)

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.5,
        max_tokens: int = 1000,
    ) -> str:
        """Generazione di testo libero."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
