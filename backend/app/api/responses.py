"""
Endpoint REST per raccolta risposte del paziente, calcolo score e
analisi multi-canale.

Flusso /responses/batch:
- Salva le risposte (audio incluso, scritto su disco).
- Se il test e' uno dei 4 cognitivi (CPT, DigitSpan, Stroop, GoNoGo):
  calcola lo score e lo salva in `cognitive_scores`.
- Se il test e' il Narrative Task: NON calcola uno score cronometrico, ma
  fa girare la pipeline multi-canale (testo o audio) e salva il risultato
  in `analysis_results`, da dove l'aggregatore lo integra nel report.
"""

import asyncio
import base64
import logging
import os
import uuid
from pathlib import Path

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
    AnalysisResult,
)
from app.schemas.api import ResponseBatchSubmit, ScoreRead, ResponseSubmit
from app.scoring.cpt_scorer import score_cpt, CPTResponse
from app.scoring.digit_span_scorer import score_digit_span, DigitSpanResponse
from app.scoring.stroop_scorer import score_stroop, StroopResponse
from app.scoring.go_nogo_scorer import score_go_nogo, GoNoGoResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/responses", tags=["responses"])

# Cartella di storage audio (condivisa con l'endpoint /analyze)
AUDIO_DIR = Path(os.getenv("AUDIO_STORAGE_DIR", "/tmp/cognitive_audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Tipi di test che producono uno score cronometrico/accuratezza
SCORED_TEST_TYPES = {"CPT", "DigitSpan", "Stroop", "GoNoGo"}
# Tipi di test valutati tramite analisi multi-canale (parlato/testo)
MULTICHANNEL_TEST_TYPES = {"Narrative"}


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def submit_responses_batch(
    payload: ResponseBatchSubmit,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Riceve tutte le risposte di un test in batch.

    - Test cognitivi: calcola e salva lo score.
    - Narrative Task: esegue e salva l'analisi multi-canale.
    """
    test_config = await db.get(TestConfiguration, payload.test_config_id)
    if not test_config or test_config.session_id != payload.session_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "TestConfiguration non trovata o non appartiene alla sessione",
        )

    # ---- Salva ogni risposta (audio incluso, scritto su disco) ----
    saved_responses: list[Response] = []
    for r in payload.responses:
        stimulus = await db.get(GeneratedStimulus, r.stimulus_id)
        if not stimulus:
            logger.warning(f"Stimulus {r.stimulus_id} non trovato, risposta saltata")
            continue

        resp = Response(
            stimulus_id=r.stimulus_id,
            session_id=payload.session_id,
            trial_index=r.trial_index,
            response_type=r.response_type,
            response_value=r.response_value,
            reaction_time_ms=r.reaction_time_ms,
        )

        # Audio: salva davvero i byte su disco e registra il path
        if r.audio_base64:
            try:
                resp.audio_path = _save_audio(r.audio_base64)
            except Exception as e:
                logger.error(f"Salvataggio audio fallito (trial {r.trial_index}): {e}")

        db.add(resp)
        saved_responses.append(resp)

    await db.flush()  # assegna gli id alle Response

    # ---- Valutazione in base al tipo di test ----
    if test_config.test_type in MULTICHANNEL_TEST_TYPES:
        analyses = await _analyze_narrative(db, test_config, saved_responses)
        await db.flush()
        return {
            "saved_responses": len(saved_responses),
            "test_type": test_config.test_type,
            "analyses": analyses,
        }

    if test_config.test_type in SCORED_TEST_TYPES:
        score = await _compute_score(db, test_config)
        return {
            "saved_responses": len(saved_responses),
            "test_type": test_config.test_type,
            "score": score.scores if score else None,
        }

    logger.warning(f"Tipo di test non gestito per la valutazione: {test_config.test_type}")
    return {"saved_responses": len(saved_responses), "test_type": test_config.test_type}


# ============================================================
# AUDIO STORAGE
# ============================================================

def _save_audio(audio_base64: str, ext: str = "wav") -> str:
    """Decodifica un audio base64 e lo scrive su disco. Ritorna il path."""
    audio_bytes = base64.b64decode(audio_base64)
    filename = f"{uuid.uuid4()}.{ext}"
    path = AUDIO_DIR / filename
    path.write_bytes(audio_bytes)
    return str(path)


# ============================================================
# ANALISI MULTI-CANALE (Narrative Task)
# ============================================================

async def _analyze_narrative(
    db: AsyncSession,
    test_config: TestConfiguration,
    responses: list[Response],
) -> list[dict]:
    """
    Esegue la pipeline multi-canale sulle risposte verbali del Narrative Task
    e SALVA il risultato in analysis_results (questo era il pezzo mancante).

    Gestisce sia audio (analyze_audio_response) sia testo (analyze_text_response).
    L'analisi gira in un threadpool per non bloccare l'event loop asincrono
    (i modelli Whisper/BERT sono lenti).
    """
    # Le funzioni sono sincrone e pesanti: importate qui per non rallentare il boot.
    from app.tasks.analysis_tasks import (
        analyze_text_response,
        analyze_audio_response,
    )

    language = (test_config.config or {}).get("language", "it")
    results: list[dict] = []

    for resp in responses:
        try:
            if resp.audio_path:
                result = await asyncio.to_thread(
                    analyze_audio_response,
                    resp.audio_path,
                    resp.id,
                    test_config.session_id,
                    language,
                    None,  # initial_prompt: non serve per parlato libero
                )
            elif resp.response_value:
                result = await asyncio.to_thread(
                    analyze_text_response,
                    resp.response_value,
                    resp.id,
                    test_config.session_id,
                    language,
                )
            else:
                logger.info(f"Risposta {resp.id} senza audio ne' testo: analisi saltata")
                continue
        except Exception as e:
            logger.exception(f"Errore analisi multi-canale (response {resp.id}): {e}")
            continue

        await _persist_multichannel(
            db,
            session_id=test_config.session_id,
            response_id=resp.id,
            result=result,
        )
        results.append(result)

    return results


async def _persist_multichannel(
    db: AsyncSession,
    session_id: str,
    response_id: str | None,
    result: dict,
) -> None:
    """
    Salva l'output del multi-canale in analysis_results.
    `features` contiene gli indici (cognitive_strain_index, ...) che
    l'aggregatore legge in _summarize_multichannel.
    """
    channels = result.get("channels_available", [])
    model_used = "multichannel-v1(" + ",".join(channels) + ")" if channels else "multichannel-v1"

    db.add(AnalysisResult(
        response_id=response_id,
        session_id=session_id,
        analysis_type="multichannel",
        features=result,
        model_used=model_used[:64],  # la colonna e' String(64)
    ))


# ============================================================
# SCORING (test cognitivi)
# ============================================================

async def _compute_score(
    db: AsyncSession,
    test_config: TestConfiguration,
) -> CognitiveScore | None:
    """Carica risposte dal DB e calcola il punteggio del test cognitivo."""
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
    stim = stimuli[0]  # un solo stimulus per CPT (contiene l'intera sequenza)
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


# ============================================================
# LETTURA RISULTATI
# ============================================================

@router.get("/scores/{session_id}", response_model=list[ScoreRead])
async def get_session_scores(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CognitiveScore]:
    """Tutti i punteggi cognitivi di una sessione."""
    stmt = select(CognitiveScore).where(CognitiveScore.session_id == session_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/analyses/{session_id}")
async def get_session_analyses(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Tutte le analisi multi-canale di una sessione.
    Utile per il report: l'aggregatore vuole la lista dei `features`
    (ogni dict contiene cognitive_strain_index, emotional_distress_index, ...).
    """
    stmt = (
        select(AnalysisResult)
        .where(
            AnalysisResult.session_id == session_id,
            AnalysisResult.analysis_type == "multichannel",
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [row.features for row in rows]
