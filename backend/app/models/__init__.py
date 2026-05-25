"""
Modelli ORM per il database.

Tabelle principali:
- patients: profilo anagrafico e clinico
- sessions: sessione di testing
- test_configurations: configurazione di un test dentro una sessione
- generated_stimuli: stimoli generati dall'LLM
- responses: risposte del paziente
- analysis_results: feature estratte da analisi
- cognitive_scores: punteggi calcolati
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


def _uuid():
    return str(uuid4())


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_code: Mapped[str] = mapped_column(String(64), unique=True)
    age: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(5), default="it")
    education_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clinical_suspicion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sensory_deficits: Mapped[dict] = mapped_column(JSON, default=dict)
    handedness: Mapped[str] = mapped_column(String(8), default="right")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["Session"]] = relationship(back_populates="patient")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    clinician_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    # draft | ready | in_progress | completed | analyzed
    session_token: Mapped[str] = mapped_column(String(64), unique=True, default=_uuid)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="sessions")
    test_configs: Mapped[list["TestConfiguration"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class TestConfiguration(Base):
    __tablename__ = "test_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    test_type: Mapped[str] = mapped_column(String(32))
    # CPT | DigitSpan | Stroop | GoNoGo
    order: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSON)  # Pydantic config dict
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship(back_populates="test_configs")
    stimuli: Mapped[list["GeneratedStimulus"]] = relationship(
        back_populates="test_config", cascade="all, delete-orphan"
    )


class GeneratedStimulus(Base):
    __tablename__ = "generated_stimuli"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    test_config_id: Mapped[str] = mapped_column(ForeignKey("test_configurations.id"))
    stimulus_data: Mapped[dict] = mapped_column(JSON)
    # output del generator (sequenza, batch, blocco, ecc.)
    llm_provider: Mapped[str] = mapped_column(String(64))
    llm_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    test_config: Mapped["TestConfiguration"] = relationship(back_populates="stimuli")
    responses: Mapped[list["Response"]] = relationship(back_populates="stimulus")


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    stimulus_id: Mapped[str] = mapped_column(ForeignKey("generated_stimuli.id"))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    trial_index: Mapped[int] = mapped_column(Integer)
    response_type: Mapped[str] = mapped_column(String(16))
    # click | key | vocal | none
    response_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reaction_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stimulus: Mapped["GeneratedStimulus"] = relationship(back_populates="responses")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    response_id: Mapped[str | None] = mapped_column(
        ForeignKey("responses.id"), nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    analysis_type: Mapped[str] = mapped_column(String(32))
    # transcription | linguistic | prosodic | sentiment | emotion
    features: Mapped[dict] = mapped_column(JSON)
    model_used: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CognitiveScore(Base):
    __tablename__ = "cognitive_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    test_config_id: Mapped[str] = mapped_column(ForeignKey("test_configurations.id"))
    test_type: Mapped[str] = mapped_column(String(32))
    scores: Mapped[dict] = mapped_column(JSON)
    # output dello scorer
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
