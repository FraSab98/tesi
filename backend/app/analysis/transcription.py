"""
Modulo di trascrizione audio con Whisper.

Whisper è il SOTA per ASR multilingua. Supporta l'italiano nativamente
e gestisce bene il parlato anziano o con disartria leggera (tipico
in pazienti MCI/Alzheimer).

Modelli disponibili (da più leggero a più accurato):
- tiny (39M params, ~10x realtime su CPU)
- base (74M, ~7x)
- small (244M, ~4x)
- medium (769M, ~2x) - raccomandato per italiano
- large-v3 (1.5B, 1x) - massima qualità, serve GPU

Per pazienti italiani su CPU consigliamo 'medium'.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False


@dataclass
class TranscriptionResult:
    """Risultato di una trascrizione."""
    text: str
    language: str
    duration_s: float
    confidence: float  # media delle avg_logprob dei segmenti (più alto = più confidente)
    segments: list  # lista di segmenti con timing word-level
    model_used: str

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "duration_s": round(self.duration_s, 2),
            "confidence": round(self.confidence, 4),
            "n_segments": len(self.segments),
            "model_used": self.model_used,
        }


class WhisperTranscriber:
    """
    Wrapper per Whisper con caching del modello.
    """

    _model_cache: dict = {}

    def __init__(self, model_size: str = "medium", device: str = "cpu"):
        if not _WHISPER_AVAILABLE:
            raise ImportError(
                "openai-whisper non installato. "
                "Installa con: pip install openai-whisper"
            )
        self.model_size = model_size
        self.device = device
        self._model = None

    def _load_model(self):
        """Lazy loading con caching: carica il modello solo alla prima trascrizione."""
        key = f"{self.model_size}:{self.device}"
        if key not in WhisperTranscriber._model_cache:
            logger.info(f"Caricamento modello Whisper '{self.model_size}' su {self.device}")
            WhisperTranscriber._model_cache[key] = whisper.load_model(
                self.model_size, device=self.device
            )
        self._model = WhisperTranscriber._model_cache[key]

    def transcribe(
        self,
        audio_path: str,
        language: str = "it",
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Trascrive un file audio.

        Args:
            audio_path: percorso al file audio (.wav, .mp3, .m4a)
            language: codice ISO (it, en, fr, ...)
            initial_prompt: suggerimento di contesto per migliorare la trascrizione.
                           Utile per Digit Span: "Il paziente ripeterà una sequenza di cifre da 1 a 9"

        Returns:
            TranscriptionResult con testo, timing, confidence
        """
        if self._model is None:
            self._load_model()

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file non trovato: {audio_path}")

        logger.info(f"Trascrizione di {path.name} ({path.stat().st_size // 1024} KB)")

        result = self._model.transcribe(
            str(path),
            language=language,
            initial_prompt=initial_prompt,
            word_timestamps=True,
            verbose=False,
        )

        # Confidence media (Whisper ritorna avg_logprob per segmento, 0 è migliore)
        segments = result.get("segments", [])
        avg_logprobs = [s.get("avg_logprob", 0) for s in segments if "avg_logprob" in s]
        # Normalizza: logprob -1 -> confidence 0.37, logprob -0.5 -> 0.6, logprob 0 -> 1.0
        import math
        confidence = math.exp(sum(avg_logprobs) / len(avg_logprobs)) if avg_logprobs else 0.0

        duration = segments[-1]["end"] if segments else 0.0

        return TranscriptionResult(
            text=result["text"].strip(),
            language=result.get("language", language),
            duration_s=duration,
            confidence=confidence,
            segments=segments,
            model_used=f"whisper-{self.model_size}",
        )


# ============ Parsing cifre per Digit Span ============

_ITALIAN_DIGIT_WORDS = {
    "zero": 0, "uno": 1, "un": 1, "due": 2, "tre": 3, "quattro": 4,
    "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "nove": 9,
}
_ENGLISH_DIGIT_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}


def parse_digit_sequence(transcript: str, language: str = "it") -> list[int]:
    """
    Estrae cifre da una trascrizione vocale.

    Gestisce sia cifre pronunciate come parole ("tre otto uno cinque")
    sia come cifre ("3 8 1 5"), e combinazioni miste.

    Args:
        transcript: testo trascritto da Whisper
        language: 'it' o 'en'

    Returns:
        Lista di cifre nell'ordine in cui appaiono

    Examples:
        >>> parse_digit_sequence("tre otto uno cinque", "it")
        [3, 8, 1, 5]
        >>> parse_digit_sequence("3 8 1 5")
        [3, 8, 1, 5]
        >>> parse_digit_sequence("trentotto ventuno")  # numeri composti non supportati per ora
        []
    """
    word_map = _ITALIAN_DIGIT_WORDS if language.startswith("it") else _ENGLISH_DIGIT_WORDS

    # Normalizza: minuscolo, separa punteggiatura
    import re
    tokens = re.findall(r"\b[\w]+\b|\d", transcript.lower())

    digits = []
    for tok in tokens:
        if tok.isdigit() and len(tok) == 1:
            digits.append(int(tok))
        elif tok.isdigit() and len(tok) > 1:
            # "385" -> [3, 8, 5] (il paziente potrebbe dirlo attaccato)
            for ch in tok:
                digits.append(int(ch))
        elif tok in word_map:
            digits.append(word_map[tok])

    return digits
