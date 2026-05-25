"""
Endpoint REST per la generazione di report clinici.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models import Session, Patient, CognitiveScore, AnalysisResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


# ============================================================
# HELPER: carica i dati grezzi della sessione dal DB
# ============================================================

async def _load_session_report_data(session_id: str, db: AsyncSession) -> dict:
    """
    Raccoglie dal DB tutto cio' che serve all'aggregatore:
    sessione, paziente, punteggi cognitivi e analisi multi-canale,
    gia' nella forma attesa da ReportAggregator.build_report().
    """
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessione non trovata")

    patient = await db.get(Patient, session.patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paziente non trovato")

    # Punteggi dei test cognitivi (CPT, DigitSpan, Stroop, GoNoGo)
    score_rows = (
        await db.execute(
            select(CognitiveScore).where(CognitiveScore.session_id == session_id)
        )
    ).scalars().all()
    test_scores = [
        {
            "test_type": s.test_type,
            "test_config_id": s.test_config_id,
            "scores": s.scores,
        }
        for s in score_rows
    ]

    # Analisi multi-canale (dal Narrative Task): lista dei `features`,
    # ognuno con cognitive_strain_index / emotional_distress_index / ...
    analysis_rows = (
        await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.session_id == session_id,
                AnalysisResult.analysis_type == "multichannel",
            )
        )
    ).scalars().all()
    analysis_results = [a.features for a in analysis_rows]

    return {
        "session": {
            "id": session.id,
            "created_at": session.created_at,
            "clinician_id": session.clinician_id,
        },
        "patient": {
            "external_code": patient.external_code,
            "age": patient.age,
            "language": patient.language,
            "clinical_suspicion": patient.clinical_suspicion,
        },
        "test_scores": test_scores,
        "analysis_results": analysis_results,
    }


# ============================================================
# REPORT DAL DB (il flusso completo che cercavi)
# ============================================================

@router.get("/session/{session_id}")
async def get_session_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Costruisce il report completo di una sessione pescando AUTOMATICAMENTE
    dal DB i punteggi dei test e le analisi multi-canale, e fondendoli con
    l'aggregatore. E' l'endpoint da chiamare a sessione completata.
    """
    from app.reporting.aggregator import ReportAggregator

    data = await _load_session_report_data(session_id, db)

    if not data["test_scores"] and not data["analysis_results"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Nessun punteggio ne' analisi per questa sessione: e' stata completata?",
        )

    aggregator = ReportAggregator()
    report = aggregator.build_report(
        session=data["session"],
        patient=data["patient"],
        test_scores=data["test_scores"],
        analysis_results=data["analysis_results"],
    )
    return report.to_dict()


@router.get("/session/{session_id}/pdf")
async def get_session_report_pdf(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Come /session/{session_id}, ma restituisce direttamente il PDF.
    Costruisce il report dal DB e poi lo rende in PDF.
    """
    from app.reporting.aggregator import ReportAggregator
    from app.reporting.pdf_generator import PDFReportGenerator

    data = await _load_session_report_data(session_id, db)

    aggregator = ReportAggregator()
    report = aggregator.build_report(
        session=data["session"],
        patient=data["patient"],
        test_scores=data["test_scores"],
        analysis_results=data["analysis_results"],
    )
    report_dict = report.to_dict()

    try:
        generator = PDFReportGenerator()
        pdf_bytes = generator.generate(report_dict)
    except ImportError:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="reportlab non installato. pip install reportlab",
        )
    except Exception as e:
        logger.exception("Errore generazione PDF")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    filename = f"report_{session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================
# REPORT DA PAYLOAD GREZZO (compatibilita': flusso esistente)
# ============================================================

@router.post("/session/build")
async def build_session_report(payload: dict):
    """
    Costruisce il report da dati grezzi passati nel payload (flusso legacy,
    utile per test o quando il frontend ha gia' i dati in mano).

    Payload atteso:
        {
          "session": {...},
          "patient": {...},
          "test_scores": [...],
          "analysis_results": [...]  # opzionale
        }
    """
    from app.reporting.aggregator import ReportAggregator

    try:
        aggregator = ReportAggregator()
        report = aggregator.build_report(
            session=payload["session"],
            patient=payload["patient"],
            test_scores=payload.get("test_scores", []),
            analysis_results=payload.get("analysis_results", []),
        )
        return report.to_dict()
    except KeyError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Campo mancante nel payload: {e}",
        )
    except Exception as e:
        logger.exception("Errore build report")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/session/pdf")
async def generate_session_pdf(payload: dict):
    """
    Genera il PDF a partire da un SessionReport gia' costruito
    (payload = output di /reports/session/build).
    """
    from app.reporting.pdf_generator import PDFReportGenerator

    try:
        generator = PDFReportGenerator()
        pdf_bytes = generator.generate(payload)

        filename = f"report_{payload.get('session_id', 'session')[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ImportError:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="reportlab non installato. pip install reportlab",
        )
    except Exception as e:
        logger.exception("Errore generazione PDF")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/longitudinal")
async def analyze_longitudinal(payload: dict):
    """
    Analisi longitudinale di piu' sessioni di uno stesso paziente.

    Payload:
        {"reports": [SessionReport, SessionReport, ...]}
    """
    from app.longitudinal.analyzer import LongitudinalAnalyzer

    reports = payload.get("reports", [])
    if not reports:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Lista 'reports' vuota",
        )

    try:
        analyzer = LongitudinalAnalyzer()
        longitudinal = analyzer.analyze_patient(reports)
        return longitudinal.to_dict()
    except Exception as e:
        logger.exception("Errore analisi longitudinale")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
