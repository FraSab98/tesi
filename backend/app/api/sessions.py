"""
Endpoint REST per sessioni di testing.
Qui avviene la magia: la creazione di una sessione invoca i generator
per ogni test configurato e salva gli stimoli generati nel DB.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import get_llm_provider
from app.models import (
    Patient,
    Session,
    TestConfiguration,
    GeneratedStimulus,
    CognitiveScore,
    AnalysisResult,
)
from app.schemas.api import (
    SessionBuild,
    SessionRead,
    SessionWithTests,
)
from app.schemas.cpt import CPTConfig
from app.schemas.digit_span import DigitSpanConfig
from app.schemas.stroop import StroopConfig
from app.schemas.go_nogo import GoNoGoConfig
from app.services.tests.cpt_generator import CPTGenerator
from app.services.tests.digit_span_generator import DigitSpanGenerator
from app.services.tests.stroop_generator import StroopGenerator
from app.services.tests.go_nogo_generator import GoNoGoGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


# Map test_type -> (ConfigSchema, GeneratorClass)
_TEST_REGISTRY = {
    "CPT": (CPTConfig, CPTGenerator),
    "DigitSpan": (DigitSpanConfig, DigitSpanGenerator),
    "Stroop": (StroopConfig, StroopGenerator),
    "GoNoGo": (GoNoGoConfig, GoNoGoGenerator),
}


@router.post("/build", response_model=SessionWithTests, status_code=status.HTTP_201_CREATED)
async def build_session(
    payload: SessionBuild,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Costruisce una sessione completa: crea la Session, le TestConfiguration,
    e genera gli stimoli per ciascun test tramite LLM.
    """
    patient = await db.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paziente non trovato",
        )

    session = Session(
        patient_id=payload.patient_id,
        clinician_id=payload.clinician_id,
        notes=payload.notes,
        status="draft",
    )
    db.add(session)
    await db.flush()

    llm = get_llm_provider()
    created_configs = []

    for test_spec in payload.tests:
        if test_spec.test_type not in _TEST_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Test type sconosciuto: {test_spec.test_type}",
            )

        ConfigSchema, GeneratorClass = _TEST_REGISTRY[test_spec.test_type]
        try:
            validated_config = ConfigSchema.model_validate(test_spec.config)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Config invalida per {test_spec.test_type}: {e}",
            )

        test_config = TestConfiguration(
            session_id=session.id,
            test_type=test_spec.test_type,
            order=test_spec.order,
            config=validated_config.model_dump(),
        )
        db.add(test_config)
        await db.flush()

        try:
            generator = GeneratorClass(llm)
            stimulus_output = await generator.generate(validated_config)
        except Exception as e:
            logger.error(f"Errore generazione {test_spec.test_type}: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Errore generazione stimoli per {test_spec.test_type}: {e}",
            )

        stimulus = GeneratedStimulus(
            test_config_id=test_config.id,
            stimulus_data=stimulus_output.model_dump(),
            llm_provider=llm.provider_name,
            llm_metadata={
                "test_type": test_spec.test_type,
                "generator_category": generator.category,
            },
        )
        db.add(stimulus)

        created_configs.append({
            "id": test_config.id,
            "test_type": test_config.test_type,
            "order": test_config.order,
            "config": test_config.config,
            "stimulus_count": _count_stimuli(stimulus_output.model_dump()),
        })

    session.status = "ready"
    await db.flush()
    await db.refresh(session)

    return {
        "id": session.id,
        "patient_id": session.patient_id,
        "clinician_id": session.clinician_id,
        "status": session.status,
        "session_token": session.session_token,
        "notes": session.notes,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "test_configs": created_configs,
    }


@router.get("", response_model=list[dict])
async def list_sessions(
    patient_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Lista tutte le sessioni con info paziente aggregate.
    Filtri opzionali: patient_id, status.
    """
    stmt = (
        select(Session, Patient)
        .join(Patient, Session.patient_id == Patient.id)
        .order_by(Session.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if patient_id:
        stmt = stmt.where(Session.patient_id == patient_id)
    if status_filter:
        stmt = stmt.where(Session.status == status_filter)

    rows = (await db.execute(stmt)).all()

    # Carichiamo anche conteggio test e score per colpo d'occhio
    out = []
    for sess, pat in rows:
        # quanti test e quanti score ha
        tc_count_stmt = select(TestConfiguration).where(TestConfiguration.session_id == sess.id)
        tc_list = (await db.execute(tc_count_stmt)).scalars().all()
        score_count_stmt = select(CognitiveScore).where(CognitiveScore.session_id == sess.id)
        score_list = (await db.execute(score_count_stmt)).scalars().all()

        out.append({
            "id": sess.id,
            "patient_id": sess.patient_id,
            "patient_code": pat.external_code,
            "patient_age": pat.age,
            "clinician_id": sess.clinician_id,
            "status": sess.status,
            "session_token": sess.session_token,
            "notes": sess.notes,
            "created_at": sess.created_at,
            "completed_at": sess.completed_at,
            "n_tests": len(tc_list),
            "n_scored": len(score_list),
            "test_types": [tc.test_type for tc in tc_list],
        })
    return out


@router.get("/{session_id}", response_model=SessionWithTests)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Recupera dettagli completi di una sessione."""
    stmt = (
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.test_configs))
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessione non trovata")

    return {
        "id": session.id,
        "patient_id": session.patient_id,
        "clinician_id": session.clinician_id,
        "status": session.status,
        "session_token": session.session_token,
        "notes": session.notes,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "test_configs": [
            {
                "id": tc.id,
                "test_type": tc.test_type,
                "order": tc.order,
                "config": tc.config,
            }
            for tc in sorted(session.test_configs, key=lambda t: t.order)
        ],
    }


@router.get("/{session_id}/stimuli")
async def get_session_stimuli(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Restituisce gli stimoli generati per tutti i test della sessione."""
    stmt = (
        select(TestConfiguration)
        .where(TestConfiguration.session_id == session_id)
        .options(selectinload(TestConfiguration.stimuli))
        .order_by(TestConfiguration.order)
    )
    configs = (await db.execute(stmt)).scalars().all()

    if not configs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessione senza test")

    return [
        {
            "test_config_id": tc.id,
            "test_type": tc.test_type,
            "order": tc.order,
            "config": tc.config,
            "stimuli": [
                {
                    "id": s.id,
                    "data": s.stimulus_data,
                    "llm_provider": s.llm_provider,
                }
                for s in tc.stimuli
            ],
        }
        for tc in configs
    ]


@router.get("/{session_id}/report")
async def get_session_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Costruisce e restituisce il report strutturato di una sessione,
    caricando direttamente dal DB. Evita al frontend di dover assemblare
    il payload manualmente.
    """
    from app.reporting.aggregator import ReportAggregator

    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessione non trovata")

    patient = await db.get(Patient, session.patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paziente non trovato")

    scores_stmt = select(CognitiveScore).where(CognitiveScore.session_id == session_id)
    scores = (await db.execute(scores_stmt)).scalars().all()

    analyses_stmt = select(AnalysisResult).where(AnalysisResult.session_id == session_id)
    analyses = (await db.execute(analyses_stmt)).scalars().all()

    if not scores:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Nessun punteggio disponibile per questa sessione — il paziente non ha ancora completato i test",
        )

    aggregator = ReportAggregator()
    report = aggregator.build_report(
        session={
            "id": session.id,
            "created_at": session.created_at,
            "clinician_id": session.clinician_id,
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
        analysis_results=[
            {"analysis_type": a.analysis_type, "features": a.features}
            for a in analyses
        ],
    )
    return report.to_dict()


def _count_stimuli(data: dict) -> int:
    """Conta il numero di stimoli in un output qualsiasi di generator."""
    if "stimuli" in data:
        return len(data["stimuli"])
    if "sequences" in data:
        return len(data["sequences"])
    if "phases" in data:
        return sum(len(p.get("trials", [])) for p in data["phases"])
    return 1
