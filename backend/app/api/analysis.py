"""
Endpoint REST per l'analisi multi-canale delle risposte.

Modalità:
- Sincrona (/analyze/text): per risposte testuali brevi -> salva subito in DB
- Asincrona (/analyze/audio): per audio, in background -> salva in DB a fine analisi
Consultazione:
- GET /analyze/results            -> elenco analisi salvate (filtrabile per sessione)
- GET /analyze/results/{id}       -> dettaglio completo di una analisi
"""

import asyncio
import base64
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.models import AnalysisResult, Patient, Session

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


# ============ PERSISTENZA ============

def _clean_id(value: Optional[str]) -> Optional[str]:
    """Scarta i placeholder ad-hoc: per le analisi di prova salviamo NULL."""
    if not value or value == "adhoc":
        return None
    return value


def _build_row(session_id: Optional[str], response_id: Optional[str], result: dict) -> AnalysisResult:
    channels = result.get("channels_available", [])
    model_used = ("multichannel-v1(" + ",".join(channels) + ")") if channels else "multichannel-v1"
    return AnalysisResult(
        session_id=_clean_id(session_id),
        response_id=_clean_id(response_id),
        analysis_type="multichannel",
        features=result,
        model_used=model_used[:64],
    )


async def _persist_with_db(db: AsyncSession, session_id, response_id, result: dict) -> str:
    """Salva usando la sessione DB della richiesta (commit gestito da get_db)."""
    row = _build_row(session_id, response_id, result)
    db.add(row)
    await db.flush()
    return row.id


async def _persist_standalone(session_id, response_id, result: dict) -> None:
    """Salva da un contesto senza richiesta (background): crea la propria sessione."""
    async with AsyncSessionLocal() as db:
        db.add(_build_row(session_id, response_id, result))
        await db.commit()


# ============ ENDPOINTS DI ANALISI ============

@router.post("/text")
async def analyze_text(payload: TextAnalysisRequest, db: AsyncSession = Depends(get_db)):
    """
    Analisi sincrona di una risposta testuale. Salva il risultato in analysis_results
    e restituisce anche l'id con cui ritrovarlo.
    """
    from app.tasks.analysis_tasks import analyze_text_response

    try:
        result = analyze_text_response(
            text=payload.text,
            response_id=payload.response_id or "adhoc",
            session_id=payload.session_id or "adhoc",
            language=payload.language,
        )
    except Exception as e:
        logger.exception("Errore analisi testo")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Errore analisi: {e}")

    analysis_id = await _persist_with_db(db, payload.session_id, payload.response_id, result)
    return {"status": "completed", "analysis_id": analysis_id, "result": result}


@router.post("/audio", response_model=AnalysisJobResponse)
async def analyze_audio(payload: AudioAnalysisRequest, background: BackgroundTasks):
    """Analisi di una risposta audio. Salva in analysis_results a fine elaborazione."""
    try:
        audio_bytes = base64.b64decode(payload.audio_base64)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"audio_base64 non valido: {e}")

    job_id = str(uuid.uuid4())
    audio_path = AUDIO_DIR / f"{job_id}.{payload.audio_format}"
    audio_path.write_bytes(audio_bytes)

    from app.tasks.analysis_tasks import analyze_audio_response, _CELERY_AVAILABLE

    if payload.async_mode and _CELERY_AVAILABLE:
        try:
            task = analyze_audio_response.delay(
                audio_path=str(audio_path),
                response_id=payload.response_id,
                session_id=payload.session_id,
                language=payload.language,
                initial_prompt=payload.initial_prompt,
            )
            return AnalysisJobResponse(
                job_id=task.id, status="queued",
                message=f"Task accodato. Poll /analyze/jobs/{task.id} per lo stato.",
            )
        except Exception as e:
            logger.warning(f"Celery fallito, fallback a BackgroundTasks: {e}")

    background.add_task(
        _run_audio_analysis_background,
        str(audio_path), payload.response_id, payload.session_id,
        payload.language, payload.initial_prompt,
    )
    return AnalysisJobResponse(
        job_id=job_id, status="processing",
        message="Elaborazione in background. Risultato salvato in analysis_results.",
    )


def _run_audio_analysis_background(audio_path, response_id, session_id, language, initial_prompt):
    """Worker background senza Celery: analizza E salva nel DB."""
    from app.tasks.analysis_tasks import analyze_audio_response
    try:
        result = analyze_audio_response(
            audio_path=audio_path, response_id=response_id, session_id=session_id,
            language=language, initial_prompt=initial_prompt,
        )
        # Salva (questa funzione e' sincrona: avvio un loop solo per la scrittura DB)
        asyncio.run(_persist_standalone(session_id, response_id, result))
        logger.info(f"Analisi audio salvata: {result.get('channels_available')}")
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
    return {"job_id": job_id, "status": task.status, "result": task.result if task.ready() else None}


# ============ ANALISI LEGATA A UN PAZIENTE (crea una sessione di sola analisi) ============

class PatientTextAnalysisRequest(BaseModel):
    patient_id: str
    text: str = Field(..., min_length=1, max_length=10000)
    language: str = Field(default="it", min_length=2, max_length=5)
    clinician_id: str = "dr_default"


class PatientAudioAnalysisRequest(BaseModel):
    patient_id: str
    audio_base64: str
    audio_format: str = Field(default="webm", pattern="^(wav|mp3|m4a|webm|ogg)$")
    language: str = "it"
    initial_prompt: Optional[str] = None
    clinician_id: str = "dr_default"


async def _create_analysis_session(db: AsyncSession, patient_id: str, clinician_id: str) -> Session:
    """Crea una sessione 'contenitore' per la sola analisi multi-canale (nessun test)."""
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paziente non trovato")
    session = Session(patient_id=patient_id, clinician_id=clinician_id, status="analyzed")
    db.add(session)
    await db.flush()  # genera session.id
    return session


@router.post("/session/text")
async def analyze_text_as_session(
    payload: PatientTextAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Analizza un testo PER un paziente: crea una sessione di sola analisi,
    esegue il multi-canale, lo salva, e restituisce il session_id per il report.
    """
    from app.tasks.analysis_tasks import analyze_text_response

    session = await _create_analysis_session(db, payload.patient_id, payload.clinician_id)
    try:
        result = analyze_text_response(
            text=payload.text, response_id="adhoc",
            session_id=session.id, language=payload.language,
        )
    except Exception as e:
        logger.exception("Errore analisi testo")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Errore analisi: {e}")

    await _persist_with_db(db, session.id, None, result)
    return {"session_id": session.id, "result": result}


@router.post("/session/audio")
async def analyze_audio_as_session(
    payload: PatientAudioAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Come /session/text, ma da audio (sincrono). Crea sessione + salva l'analisi."""
    from app.tasks.analysis_tasks import analyze_audio_response

    try:
        audio_bytes = base64.b64decode(payload.audio_base64)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"audio_base64 non valido: {e}")

    session = await _create_analysis_session(db, payload.patient_id, payload.clinician_id)
    audio_path = AUDIO_DIR / f"{session.id}.{payload.audio_format}"
    audio_path.write_bytes(audio_bytes)

    try:
        result = await asyncio.to_thread(
            analyze_audio_response, str(audio_path), "adhoc",
            session.id, payload.language, payload.initial_prompt,
        )
    except Exception as e:
        logger.exception("Errore analisi audio")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Errore analisi: {e}")

    await _persist_with_db(db, session.id, None, result)
    return {"session_id": session.id, "result": result}


# ============ CONSULTAZIONE ANALISI SALVATE ============

@router.get("/results")
async def list_analysis_results(
    session_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Elenco delle analisi salvate (piu' recenti prima), con i campi sintetici.
    Filtrabile per sessione: /analyze/results?session_id=...
    """
    stmt = select(AnalysisResult).order_by(desc(AnalysisResult.created_at)).limit(min(limit, 200))
    if session_id:
        stmt = stmt.where(AnalysisResult.session_id == session_id)
    rows = (await db.execute(stmt)).scalars().all()

    out = []
    for r in rows:
        f = r.features or {}
        out.append({
            "id": r.id,
            "session_id": r.session_id,
            "response_id": r.response_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "model_used": r.model_used,
            "transcript": f.get("transcript"),
            "cognitive_strain_index": f.get("cognitive_strain_index"),
            "emotional_distress_index": f.get("emotional_distress_index"),
            "communication_quality_index": f.get("communication_quality_index"),
            "channels_available": f.get("channels_available", []),
        })
    return out


@router.get("/results/{result_id}")
async def get_analysis_result(result_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Dettaglio completo di una singola analisi salvata (tutte le features)."""
    row = await db.get(AnalysisResult, result_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analisi non trovata")
    return {
        "id": row.id,
        "session_id": row.session_id,
        "response_id": row.response_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "analysis_type": row.analysis_type,
        "model_used": row.model_used,
        "features": row.features,
    }
