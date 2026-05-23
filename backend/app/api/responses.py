"""
Endpoint REST per raccolta risposte del paziente e calcolo score.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import (
    Session,
    TestConfiguration,
    GeneratedStimulus,
    Response,
    CognitiveScore,
)
from app.schemas.api import ResponseBatchSubmit, ScoreRead
from app.scoring.cpt_scorer import score_cpt, CPTResponse
from app.scoring.digit_span_scorer import score_digit_span, DigitSpanResponse
from app.scoring.stroop_scorer import score_stroop, StroopResponse
from app.scoring.go_nogo_scorer import score_go_nogo, GoNoGoResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/responses", tags=["responses"])


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def submit_responses_batch(
    payload: ResponseBatchSubmit,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Riceve tutte le risposte di un test in batch e calcola immediatamente
    il punteggio. Per le risposte vocali (Digit Span), l'audio viene salvato
    e la trascrizione avviene asincrona tramite Celery (non implementato in
    questo MVP ma il gancio è predisposto).
    """
    # Verifica sessione e test config
    test_config = await db.get(TestConfiguration, payload.test_config_id)
    if not test_config or test_config.session_id != payload.session_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "TestConfiguration non trovata o non appartiene alla sessione",
        )

    # Salva ogni risposta
    saved_responses = []
    for r in payload.responses:
        stimulus = await db.get(GeneratedStimulus, r.stimulus_id)
        if not stimulus:
            continue

        resp = Response(
            stimulus_id=r.stimulus_id,
            session_id=payload.session_id,
            trial_index=r.trial_index,
            response_type=r.response_type,
            response_value=r.response_value,
            reaction_time_ms=r.reaction_time_ms,
        )

        # Audio: in MVP salviamo solo che esiste, upload a MinIO nella Fase 6
        if r.audio_base64:
            resp.audio_path = f"pending_upload_{r.stimulus_id}.wav"

        db.add(resp)
        saved_responses.append(resp)

    await db.flush()

    # Calcola score sul test
    score = await _compute_score(db, test_config)

    return {
        "saved_responses": len(saved_responses),
        "score": score.scores if score else None,
    }


async def _compute_score(
    db: AsyncSession,
    test_config: TestConfiguration,
) -> CognitiveScore | None:
    """Carica risposte dal DB e calcola il punteggio del test."""
    # Carica stimuli + risposte
    stmt = (
        select(GeneratedStimulus)
        .where(GeneratedStimulus.test_config_id == test_config.id)
        .options(selectinload(GeneratedStimulus.responses))
    )
    stimuli = (await db.execute(stmt)).scalars().all()

    if not stimuli:
        return None

    scorer_fn = _SCORER_REGISTRY.get(test_config.test_type)
    if not scorer_fn:
        logger.warning(f"Nessuno scorer per {test_config.test_type}")
        return None

    try:
        score_obj = scorer_fn(stimuli)
    except Exception as e:
        logger.error(f"Errore scoring {test_config.test_type}: {e}")
        return None

    # Salva nel DB
    score_record = CognitiveScore(
        session_id=test_config.session_id,
        test_config_id=test_config.id,
        test_type=test_config.test_type,
        scores=score_obj.to_dict(),
    )
    db.add(score_record)
    await db.flush()
    return score_record


# ============ SCORERS ADAPTERS ============

def _score_cpt_from_db(stimuli: list[GeneratedStimulus]):
    """Adatta dati DB al formato CPTResponse e chiama lo scorer."""
    # Un solo stimulus per CPT (contiene l'intera sequenza)
    stim = stimuli[0]
    seq = stim.stimulus_data.get("stimuli", [])
    resp_by_idx = {r.trial_index: r for r in stim.responses}

    cpt_responses = []
    for i, s in enumerate(seq):
        r = resp_by_idx.get(i)
        responded = r is not None and r.response_type != "none"
        rt = r.reaction_time_ms if r else None
        cpt_responses.append(CPTResponse(
            stimulus_index=i,
            stimulus=s["stimulus"],
            is_target=s["is_target"],
            responded=responded,
            reaction_time_ms=rt,
        ))
    return score_cpt(cpt_responses)


def _score_digit_span_from_db(stimuli: list[GeneratedStimulus]):
    """Adatta e chiama lo scorer Digit Span."""
    ds_responses = []
    mode = "forward"
    for stim in stimuli:
        data = stim.stimulus_data
        mode = data.get("mode", mode)
        sequences = data.get("sequences", [])
        resp_by_idx = {r.trial_index: r for r in stim.responses}
        for i, seq_obj in enumerate(sequences):
            r = resp_by_idx.get(i)
            target = seq_obj["sequence"]
            # response_value conterrà la sequenza trascritta es. "3 8 1 5"
            response_seq = []
            if r and r.response_value:
                try:
                    response_seq = [int(x) for x in r.response_value.split() if x.isdigit()]
                except ValueError:
                    response_seq = []
            ds_responses.append(DigitSpanResponse(
                target_sequence=target,
                response_sequence=response_seq,
                length=len(target),
            ))
    return score_digit_span(ds_responses, mode=mode)


def _score_stroop_from_db(stimuli: list[GeneratedStimulus]):
    """Stroop: raggruppa per block type."""
    blocks_by_type = {"word": [], "color": [], "color_word": []}
    for stim in stimuli:
        data = stim.stimulus_data
        block_type = data.get("condition")
        if block_type not in blocks_by_type:
            continue
        resp_by_idx = {r.trial_index: r for r in stim.responses}
        for i, s in enumerate(data.get("stimuli", [])):
            r = resp_by_idx.get(i)
            # Correttezza: nello Stroop il paziente deve nominare l'ink_color
            correct = False
            if r and r.response_value:
                correct = r.response_value.lower() == s["ink_color"].lower()
            blocks_by_type[block_type].append(StroopResponse(
                stimulus_index=i,
                word=s["word"],
                ink_color=s["ink_color"],
                condition=s["condition"],
                response_color=r.response_value if r else None,
                reaction_time_ms=r.reaction_time_ms if r else None,
                correct=correct,
            ))
    return score_stroop(
        word_block=blocks_by_type["word"] or None,
        color_block=blocks_by_type["color"] or None,
        color_word_block=blocks_by_type["color_word"] or None,
    )


def _score_go_nogo_from_db(stimuli: list[GeneratedStimulus]):
    """Go/No-Go: adatta fasi a GoNoGoResponse."""
    stim = stimuli[0]
    phases = stim.stimulus_data.get("phases", [])
    resp_by_idx = {r.trial_index: r for r in stim.responses}

    gn_responses = []
    global_idx = 0
    for phase_obj in phases:
        phase_name = phase_obj["phase"]
        for trial in phase_obj.get("trials", []):
            r = resp_by_idx.get(global_idx)
            responded = r is not None and r.response_type != "none"
            rt = r.reaction_time_ms if r else None
            gn_responses.append(GoNoGoResponse(
                trial_index=global_idx,
                phase=phase_name,
                stimulus_type=trial["stimulus_type"],
                responded=responded,
                reaction_time_ms=rt,
            ))
            global_idx += 1
    return score_go_nogo(gn_responses)


_SCORER_REGISTRY = {
    "CPT": _score_cpt_from_db,
    "DigitSpan": _score_digit_span_from_db,
    "Stroop": _score_stroop_from_db,
    "GoNoGo": _score_go_nogo_from_db,
}


@router.get("/scores/{session_id}", response_model=list[ScoreRead])
async def get_session_scores(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CognitiveScore]:
    """Tutti i punteggi di una sessione."""
    stmt = select(CognitiveScore).where(CognitiveScore.session_id == session_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
