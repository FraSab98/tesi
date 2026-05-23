"""
Schemi Pydantic per request/response delle API.
Separati dagli schemi di test (che definiscono gli stimoli).
"""

from datetime import datetime
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


# ================= PATIENTS =================

class PatientCreate(BaseModel):
    external_code: str = Field(..., min_length=1, max_length=64)
    age: int = Field(..., ge=5, le=120)
    language: str = Field(default="it", min_length=2, max_length=5)
    education_years: Optional[int] = Field(None, ge=0, le=30)
    clinical_suspicion: Optional[
        Literal["MCI", "Alzheimer", "ADHD", "Parkinson", "none"]
    ] = None
    sensory_deficits: dict = Field(default_factory=dict)
    handedness: Literal["right", "left", "ambidextrous"] = "right"


class PatientRead(PatientCreate):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ================= SESSIONS =================

class SessionCreate(BaseModel):
    patient_id: str
    clinician_id: str
    notes: Optional[str] = None


class TestConfigInSession(BaseModel):
    test_type: Literal["CPT", "DigitSpan", "Stroop", "GoNoGo"]
    order: int = 0
    config: dict  # corrispondente al config schema del test


class SessionBuild(BaseModel):
    """Richiesta per costruire una sessione completa con la batteria di test."""
    patient_id: str
    clinician_id: str
    tests: list[TestConfigInSession] = Field(..., min_length=1)
    notes: Optional[str] = None


class SessionRead(BaseModel):
    id: str
    patient_id: str
    clinician_id: str
    status: str
    session_token: str
    notes: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SessionWithTests(SessionRead):
    test_configs: list[dict]


# ================= STIMULI =================

class StimulusRead(BaseModel):
    id: str
    test_config_id: str
    stimulus_data: dict
    llm_provider: str
    generated_at: datetime

    class Config:
        from_attributes = True


# ================= RESPONSES =================

class ResponseSubmit(BaseModel):
    stimulus_id: str
    session_id: str
    trial_index: int
    response_type: Literal["click", "key", "vocal", "none"]
    response_value: Optional[str] = None
    reaction_time_ms: Optional[float] = Field(None, ge=0)
    audio_base64: Optional[str] = Field(None, description="Audio codificato base64 per upload")


class ResponseBatchSubmit(BaseModel):
    """Batch submit: invia tutte le risposte di un test insieme."""
    session_id: str
    test_config_id: str
    responses: list[ResponseSubmit]


# ================= SCORES =================

class ScoreRead(BaseModel):
    id: str
    session_id: str
    test_config_id: str
    test_type: str
    scores: dict
    computed_at: datetime

    class Config:
        from_attributes = True


class SessionReport(BaseModel):
    """Report completo di una sessione per il medico."""
    session: SessionRead
    patient: PatientRead
    scores: list[ScoreRead]
    analyses: list[dict]
