"""
Endpoint REST per la gestione dei pazienti.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models import Patient, Session, CognitiveScore, AnalysisResult
from app.schemas.api import PatientCreate, PatientRead

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    db: AsyncSession = Depends(get_db),
) -> Patient:
    """Crea un nuovo paziente."""
    stmt = select(Patient).where(Patient.external_code == payload.external_code)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Paziente con external_code='{payload.external_code}' già esistente",
        )

    patient = Patient(**payload.model_dump())
    db.add(patient)
    await db.flush()
    await db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> Patient:
    """Recupera un paziente per ID."""
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paziente non trovato",
        )
    return patient


@router.get("", response_model=list[PatientRead])
async def list_patients(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[Patient]:
    """Lista pazienti con paginazione."""
    stmt = select(Patient).order_by(Patient.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{patient_id}/reports")
async def list_patient_reports(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Restituisce la lista dei report strutturati per tutte le sessioni
    di un paziente che hanno almeno un punteggio. Utile per l'analisi
    longitudinale.
    """
    from app.reporting.aggregator import ReportAggregator

    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paziente non trovato")

    sessions_stmt = (
        select(Session)
        .where(Session.patient_id == patient_id)
        .order_by(Session.created_at.asc())
    )
    sessions = (await db.execute(sessions_stmt)).scalars().all()

    aggregator = ReportAggregator()
    reports: list[dict] = []

    for sess in sessions:
        scores_stmt = select(CognitiveScore).where(CognitiveScore.session_id == sess.id)
        scores = (await db.execute(scores_stmt)).scalars().all()

        analyses_stmt = select(AnalysisResult).where(AnalysisResult.session_id == sess.id)
        analyses = (await db.execute(analyses_stmt)).scalars().all()

        if not scores and not analyses:
            continue  # skip solo le sessioni senza alcun dato

        report = aggregator.build_report(
            session={
                "id": sess.id,
                "created_at": sess.created_at,
                "clinician_id": sess.clinician_id,
            },
            patient={
                "external_code": patient.external_code,
                "age": patient.age,
                "language": patient.language,
                "clinical_suspicion": patient.clinical_suspicion,
            },
            test_scores=[
                {
                    "test_type": s.test_type,
                    "test_config_id": s.test_config_id,
                    "scores": s.scores,
                }
                for s in scores
            ],
            analysis_results=[a.features for a in analyses],
        )
        reports.append(report.to_dict())

    return reports
