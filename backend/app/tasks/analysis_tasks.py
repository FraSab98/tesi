"""
Task Celery per analisi asincrona delle risposte audio.

Le pipeline NLP/prosodia/emotion sono lente (specie se usano modelli
pesanti come Whisper medium o BERT): non possiamo bloccare la richiesta
HTTP del paziente in attesa. Usiamo Celery + Redis per processarle in
background.

Flusso:
1. Il paziente invia una risposta audio → endpoint salva audio e
   accoda task Celery.
2. Il worker Celery estrae feature tramite MultiChannelAnalyzer.
3. I risultati vengono salvati in analysis_results del DB.
4. Il medico vede i risultati quando sono pronti (refresh o websocket).
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from celery import Celery
    _CELERY_AVAILABLE = True
except ImportError:
    _CELERY_AVAILABLE = False
    Celery = None

# ============ Celery app ============

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if _CELERY_AVAILABLE:
    celery_app = Celery(
        "cognitive_analysis",
        broker=REDIS_URL,
        backend=REDIS_URL,
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_time_limit=300,    # 5 min max per task
        task_soft_time_limit=240,
        worker_prefetch_multiplier=1,  # evita che un worker si prenoti troppi task
    )
else:
    celery_app = None


# ============ Task ============

def _build_analyzer(language: str = "it", enable_prosodic: bool = True,
                     enable_emotion: bool = True, whisper_size: str = "medium"):
    """Factory che costruisce l'analizzatore a seconda dei moduli disponibili."""
    from app.analysis.multichannel import MultiChannelAnalyzer

    transcriber = linguistic = prosodic = sentiment = emotion = None

    try:
        from app.analysis.transcription import WhisperTranscriber
        transcriber = WhisperTranscriber(model_size=whisper_size)
    except ImportError:
        logger.warning("Whisper non disponibile, trascrizione saltata")

    try:
        from app.analysis.linguistic import LinguisticAnalyzer
        model = "it_core_news_lg" if language == "it" else "en_core_web_lg"
        linguistic = LinguisticAnalyzer(model=model)
    except (ImportError, OSError) as e:
        logger.warning(f"Linguistic analyzer non disponibile: {e}")

    if enable_prosodic:
        try:
            from app.analysis.prosodic import ProsodicAnalyzer
            prosodic = ProsodicAnalyzer()
        except ImportError:
            logger.warning("Librosa non disponibile, prosodia saltata")

    if enable_emotion:
        try:
            from app.analysis.sentiment_emotion import SentimentAnalyzer, EmotionAnalyzer
            sentiment = SentimentAnalyzer(language=language)
            emotion = EmotionAnalyzer(language=language)
        except ImportError:
            logger.warning("Transformers non disponibile, sentiment/emotion saltati")

    return MultiChannelAnalyzer(
        transcriber=transcriber,
        linguistic_analyzer=linguistic,
        prosodic_analyzer=prosodic,
        sentiment_analyzer=sentiment,
        emotion_analyzer=emotion,
        language=language,
    )


def analyze_audio_response(
    audio_path: str,
    response_id: str,
    session_id: str,
    language: str = "it",
    initial_prompt: Optional[str] = None,
) -> dict:
    """
    Task di analisi di una risposta audio.
    Funzione pura chiamabile sia sincrona (test/demo) sia come task Celery.
    """
    logger.info(f"Inizio analisi audio: response_id={response_id}")

    analyzer = _build_analyzer(language=language)
    result = analyzer.analyze_audio(audio_path, initial_prompt=initial_prompt)

    logger.info(
        f"Analisi completata in {result.analysis_duration_s:.1f}s, "
        f"canali: {result.channels_available}"
    )

    return result.to_dict()


def analyze_text_response(
    text: str,
    response_id: str,
    session_id: str,
    language: str = "it",
) -> dict:
    """Task di analisi per risposte testuali (senza audio)."""
    logger.info(f"Inizio analisi testo: response_id={response_id}")

    analyzer = _build_analyzer(language=language)
    result = analyzer.analyze_text(text)

    logger.info(f"Analisi completata in {result.analysis_duration_s:.1f}s")
    return result.to_dict()


# Registra come task Celery se disponibile
if _CELERY_AVAILABLE:
    analyze_audio_response = celery_app.task(
        name="analyze_audio_response"
    )(analyze_audio_response)
    analyze_text_response = celery_app.task(
        name="analyze_text_response"
    )(analyze_text_response)
