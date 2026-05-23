"""
Implementazione del LLMProvider che usa le API di Anthropic Claude.
Sfrutta il meccanismo di "tool use" per forzare output JSON strutturato.
"""

import json
import logging
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # lazy import: anthropic è opzionale

from .provider import LLMProvider, GenerationFailedError

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AnthropicProvider(LLMProvider):
    """Provider che usa Claude via API Anthropic."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        max_retries: int = 3,
    ):
        if AsyncAnthropic is None:
            raise ImportError(
                "Installare con `pip install anthropic` per usare AnthropicProvider"
            )
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    @property
    def provider_name(self) -> str:
        return f"anthropic:{self.model}"

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> T:
        """
        Usa il "tool use" di Anthropic per forzare output JSON conforme.
        In caso di errore di validazione, retry con feedback.
        """
        schema_json = output_schema.model_json_schema()

        tools = [{
            "name": "return_structured_data",
            "description": f"Ritorna dati strutturati conformi a {output_schema.__name__}",
            "input_schema": schema_json,
        }]

        current_user_prompt = user_prompt
        last_error = ""

        for attempt in range(self.max_retries):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    tools=tools,
                    tool_choice={"type": "tool", "name": "return_structured_data"},
                    messages=[{"role": "user", "content": current_user_prompt}],
                )

                # Estrai il tool_use block
                tool_block = next(
                    (b for b in response.content if b.type == "tool_use"),
                    None
                )
                if not tool_block:
                    raise ValueError("Nessun tool_use nella risposta")

                # Valida contro lo schema
                validated = output_schema.model_validate(tool_block.input)
                logger.info(
                    f"[{self.provider_name}] Generazione riuscita al tentativo {attempt+1}"
                )
                return validated

            except ValidationError as e:
                last_error = str(e)
                logger.warning(
                    f"[{self.provider_name}] Tentativo {attempt+1} fallito: {last_error[:200]}"
                )
                # Arricchisci il prompt con l'errore per il retry
                current_user_prompt = (
                    f"{user_prompt}\n\n"
                    f"Il tuo tentativo precedente è fallito con questo errore di validazione:\n"
                    f"{last_error}\n\n"
                    f"Correggi il problema e riprova."
                )
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.error(
                    f"[{self.provider_name}] Errore API al tentativo {attempt+1}: {last_error}"
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
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_blocks = [b for b in response.content if b.type == "text"]
        return "".join(b.text for b in text_blocks)
