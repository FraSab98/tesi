"""
Endpoint REST per la generazione di report clinici.
"""

import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/session/build")
async def build_session_report(payload: dict):
    """
    Costruisce il report strutturato di una sessione a partire dai dati grezzi.

    Payload atteso:
        {
          "session": {...},
          "patient": {...},
          "test_scores": [...],
          "analysis_results": [...]  # opzionale, dalla Fase 6
        }

    Questo endpoint è pensato per essere chiamato internamente dopo il
    completamento di una sessione; in alternativa, i dati possono venire
    caricati direttamente dal DB con /reports/session/{id} (non incluso nel MVP).
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
    Genera il PDF del report di sessione.

    Accetta direttamente un SessionReport già costruito (payload = output di /reports/session/build),
    per semplicità del flusso: il frontend costruisce il report, lo visualizza,
    e poi chiede il PDF con gli stessi dati.

    Returns:
        PDF come application/pdf
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
    Analisi longitudinale di più sessioni di uno stesso paziente.

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
