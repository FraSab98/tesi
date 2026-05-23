"""
Sentiment ed Emotion Analysis con modelli HuggingFace.

Modelli consigliati per italiano:
- sentiment: 'neuraly/bert-base-italian-cased-sentiment' (pos/neg)
- emotion:   'MilaNLProc/feel-it-italian-emotion' (joy/anger/fear/sadness)

Questi modelli sono usati per:
- Rilevare frustrazione/ansia durante i test
- Identificare pattern emotivi nelle narrazioni (SDM, Paper 11)
- Correlare stato emotivo e performance cognitiva
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from transformers import pipeline
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False


@dataclass
class SentimentResult:
    """Risultato sentiment analysis."""
    label: str           # 'positive', 'negative', 'neutral'
    score: float         # 0-1 confidence
    model_used: str

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "score": round(self.score, 4),
            "model_used": self.model_used,
        }


@dataclass
class EmotionResult:
    """Risultato emotion analysis."""
    emotions: dict = field(default_factory=dict)  # {emotion: score}
    dominant: str = ""
    dominant_score: float = 0.0
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "emotions": {k: round(v, 4) for k, v in self.emotions.items()},
            "dominant": self.dominant,
            "dominant_score": round(self.dominant_score, 4),
            "model_used": self.model_used,
        }


class SentimentAnalyzer:
    """Sentiment analysis con modelli HuggingFace."""

    _pipeline_cache: dict = {}

    # Modelli default per lingua
    DEFAULT_MODELS = {
        "it": "neuraly/bert-base-italian-cased-sentiment",
        "en": "distilbert-base-uncased-finetuned-sst-2-english",
    }

    def __init__(self, language: str = "it", model: Optional[str] = None):
        if not _TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers non installato. "
                "Installa con: pip install transformers torch"
            )
        self.language = language
        self.model_name = model or self.DEFAULT_MODELS.get(language, self.DEFAULT_MODELS["en"])
        self._pipeline = None

    def _load_pipeline(self):
        if self.model_name not in SentimentAnalyzer._pipeline_cache:
            logger.info(f"Caricamento pipeline sentiment '{self.model_name}'")
            SentimentAnalyzer._pipeline_cache[self.model_name] = pipeline(
                "sentiment-analysis",
                model=self.model_name,
                top_k=None,  # restituisci tutte le classi
            )
        self._pipeline = SentimentAnalyzer._pipeline_cache[self.model_name]

    def analyze(self, text: str) -> SentimentResult:
        """Analizza il sentiment di un testo."""
        if not text or len(text.strip()) < 3:
            return SentimentResult(
                label="neutral",
                score=0.0,
                model_used=self.model_name,
            )

        if self._pipeline is None:
            self._load_pipeline()

        # Troncatura a 512 token (limite BERT)
        truncated = text[:2000]

        result = self._pipeline(truncated)
        # Il pipeline ritorna [[{'label': X, 'score': Y}, ...]]
        scores = result[0] if isinstance(result[0], list) else result
        best = max(scores, key=lambda s: s["score"])

        # Normalizza label: alcuni modelli usano POSITIVE/NEGATIVE, altri pos/neg
        label_normalized = best["label"].lower()
        if "pos" in label_normalized:
            label_normalized = "positive"
        elif "neg" in label_normalized:
            label_normalized = "negative"
        elif "neu" in label_normalized:
            label_normalized = "neutral"

        return SentimentResult(
            label=label_normalized,
            score=best["score"],
            model_used=self.model_name,
        )


class EmotionAnalyzer:
    """Emotion analysis con modelli HuggingFace."""

    _pipeline_cache: dict = {}

    DEFAULT_MODELS = {
        "it": "MilaNLProc/feel-it-italian-emotion",
        "en": "j-hartmann/emotion-english-distilroberta-base",
    }

    def __init__(self, language: str = "it", model: Optional[str] = None):
        if not _TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers non installato. "
                "Installa con: pip install transformers torch"
            )
        self.language = language
        self.model_name = model or self.DEFAULT_MODELS.get(language, self.DEFAULT_MODELS["en"])
        self._pipeline = None

    def _load_pipeline(self):
        if self.model_name not in EmotionAnalyzer._pipeline_cache:
            logger.info(f"Caricamento pipeline emotion '{self.model_name}'")
            EmotionAnalyzer._pipeline_cache[self.model_name] = pipeline(
                "text-classification",
                model=self.model_name,
                top_k=None,
            )
        self._pipeline = EmotionAnalyzer._pipeline_cache[self.model_name]

    def analyze(self, text: str) -> EmotionResult:
        """Analizza le emozioni di un testo."""
        if not text or len(text.strip()) < 3:
            return EmotionResult(model_used=self.model_name)

        if self._pipeline is None:
            self._load_pipeline()

        truncated = text[:2000]
        result = self._pipeline(truncated)
        scores = result[0] if isinstance(result[0], list) else result

        emotions = {s["label"]: s["score"] for s in scores}
        dominant = max(emotions.items(), key=lambda x: x[1])

        return EmotionResult(
            emotions=emotions,
            dominant=dominant[0],
            dominant_score=dominant[1],
            model_used=self.model_name,
        )
