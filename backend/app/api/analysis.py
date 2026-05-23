"""
Endpoint REST per l'analisi multi-canale delle risposte.

Due modalità:
- Sincrona (/analyze/text): per risposte testuali brevi
- Asincrona (/analyze/audio): per audio, accoda task Celery
"""

import base64
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analysis"])

AUDIO_DIR = Path(os.getenv("AUDIO_STORAGE_DIR", "/tmp/cognitive_audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ============ SCHEMAS ============

class TextAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    language: str = Field(default="it", min_length=2, max_length=5)
    response_id: Optional[str] = None
    session_id: Optional[str] = None


class AudioAnalysisRequest(BaseModel):
    audio_base64: str = Field(..., description="Audio file encoded in base64")
    audio_format: str = Field(default="wav", pattern="^(wav|mp3|m4a|webm|ogg)$")
    language: str = Field(default="it")
    response_id: str
    session_id: str
    initial_prompt: Optional[str] = Field(
        None,
        description="Contesto opzionale per migliorare la trascrizione (es. 'cifre da 1 a 9')",
    )
    async_mode: bool = Field(
        default=True,
        description="Se True, elabora in background (consigliato per audio lunghi)",
    )


class AnalysisJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ============ ENDPOINTS ============

@router.post("/text")
async def analyze_text(payload: TextAnalysisRequest):
    """
    Analisi sincrona di una risposta testuale.
    Usa per Digit Span (trascrizione già parseggiata) o SDM scritte.
    """
    from app.tasks.analysis_tasks import analyze_text_response

    try:
        result = analyze_text_response(
            text=payload.text,
            response_id=payload.response_id or "adhoc",
            session_id=payload.session_id or "adhoc",
            language=payload.language,
        )
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.exception("Errore analisi testo")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore analisi: {e}",
        )


@router.post("/audio", response_model=AnalysisJobResponse)
async def analyze_audio(
    payload: AudioAnalysisRequest,
    background: BackgroundTasks,
):
    """
    Analisi di una risposta audio.

    - async_mode=True (default): salva l'audio, accoda task Celery,
      restituisce subito un job_id.
    - async_mode=False: elabora in background con BackgroundTasks FastAPI
      (per deploy senza Celery).
    """
    # Salva l'audio su disco
    try:
        audio_bytes = base64.b64decode(payload.audio_base64)
    except Exception as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"audio_base64 non valido: {e}",
        )

    job_id = str(uuid.uuid4())
    audio_filename = f"{job_id}.{payload.audio_format}"
    audio_path = AUDIO_DIR / audio_filename
    audio_path.write_bytes(audio_bytes)

    from app.tasks.analysis_tasks import analyze_audio_response, _CELERY_AVAILABLE

    if payload.async_mode and _CELERY_AVAILABLE:
        # Accoda task Celery (richiede worker attivo)
        try:
            task = analyze_audio_response.delay(
                audio_path=str(audio_path),
                response_id=payload.response_id,
                session_id=payload.session_id,
                language=payload.language,
                initial_prompt=payload.initial_prompt,
            )
            return AnalysisJobResponse(
                job_id=task.id,
                status="queued",
                message=f"Task accodato. Poll /analyze/jobs/{task.id} per lo stato.",
            )
        except Exception as e:
            logger.warning(f"Celery fallito, fallback a BackgroundTasks: {e}")

    # Fallback: esecuzione in background con FastAPI
    background.add_task(
        _run_audio_analysis_background,
        str(audio_path),
        payload.response_id,
        payload.session_id,
        payload.language,
        payload.initial_prompt,
    )
    return AnalysisJobResponse(
        job_id=job_id,
        status="processing",
        message="Elaborazione in background. Risultati salvati in analysis_results.",
    )


def _run_audio_analysis_background(
    audio_path: str,
    response_id: str,
    session_id: str,
    language: str,
    initial_prompt: Optional[str],
):
    """Worker background senza Celery."""
    from app.tasks.analysis_tasks import analyze_audio_response
    try:
        result = analyze_audio_response(
            audio_path=audio_path,
            response_id=response_id,
            session_id=session_id,
            language=language,
            initial_prompt=initial_prompt,
        )
        # TODO: qui dovremmo salvare in DB via async session
        logger.info(f"Analisi completata: {result['channels_available']}")
    except Exception as e:
        logger.exception(f"Errore analisi background: {e}")


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Consulta lo stato di un task Celery."""
    from app.tasks.analysis_tasks import celery_app, _CELERY_AVAILABLE

    if not _CELERY_AVAILABLE:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="Celery non configurato. Usa async_mode=False o configura Redis.",
        )

    task = celery_app.AsyncResult(job_id)
    return {
        "job_id": job_id,
        "status": task.status,
        "result": task.result if task.ready() else None,
    }
