"""
Unit test per i moduli di analisi.

Usa mock per evitare il download di modelli pesanti (Whisper, BERT, spaCy).
I test verificano la logica di integrazione, non la qualità degli ML models.
"""

import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from app.analysis.multichannel import MultiChannelAnalyzer, MultiChannelAnalysis
from app.analysis.transcription import parse_digit_sequence


# ============ Digit sequence parsing ============

class TestDigitParsing:
    def test_parse_italian_words(self):
        assert parse_digit_sequence("tre otto uno cinque", "it") == [3, 8, 1, 5]

    def test_parse_separated_digits(self):
        assert parse_digit_sequence("3 8 1 5") == [3, 8, 1, 5]

    def test_parse_attached_digits(self):
        assert parse_digit_sequence("3815") == [3, 8, 1, 5]

    def test_parse_mixed(self):
        assert parse_digit_sequence("tre 8 uno 5", "it") == [3, 8, 1, 5]

    def test_parse_english(self):
        assert parse_digit_sequence("three eight one five", "en") == [3, 8, 1, 5]

    def test_ignores_noise(self):
        # Parole non-cifre ignorate
        assert parse_digit_sequence("allora tre otto uno cinque grazie", "it") == [3, 8, 1, 5]


# ============ MultiChannelAnalyzer con mock ============

@dataclass
class MockTranscriptionResult:
    text: str
    language: str = "it"
    duration_s: float = 3.5
    confidence: float = 0.95
    segments: list = None
    model_used: str = "mock"


@dataclass
class MockLinguisticFeatures:
    word_count: int = 50
    sentence_count: int = 5
    mean_sentence_length: float = 10.0
    lexical_diversity: float = 0.7
    mattr: float = 0.65
    lexical_density: float = 0.55
    cohesion: float = 0.20
    mean_syntactic_depth: float = 2.5
    pos_distribution: dict = None
    function_word_freq: dict = None
    pronoun_distribution: dict = None

    def to_dict(self):
        return {
            "word_count": self.word_count,
            "lexical_diversity": self.lexical_diversity,
            "mattr": self.mattr,
            "lexical_density": self.lexical_density,
            "cohesion": self.cohesion,
        }


@dataclass
class MockProsodicFeatures:
    duration_s: float = 3.5
    mean_pitch_hz: float = 180.0
    pitch_std_hz: float = 30.0
    pitch_range_hz: float = 120.0
    mean_energy: float = 0.05
    energy_std: float = 0.02
    speech_rate_proxy: float = 0.1
    pause_ratio: float = 0.15
    n_pauses: int = 3
    jitter: float = 0.03
    shimmer: float = 0.04
    mfcc_mean: list = None
    mfcc_std: list = None

    def to_dict(self):
        return {
            "duration_s": self.duration_s,
            "mean_pitch_hz": self.mean_pitch_hz,
            "pitch_std_hz": self.pitch_std_hz,
            "pause_ratio": self.pause_ratio,
            "jitter": self.jitter,
        }


class TestMultiChannelAnalyzer:
    def _build_healthy_analyzer(self):
        """Analyzer mockato per profilo sano."""
        transcriber = MagicMock()
        transcriber.transcribe.return_value = MockTranscriptionResult(
            text="Racconto di quando sono andato in montagna con mio padre. "
                 "Era un giorno bellissimo e abbiamo camminato insieme."
        )

        linguistic = MagicMock()
        linguistic.analyze.return_value = MockLinguisticFeatures(
            word_count=50, mattr=0.70, lexical_density=0.60, cohesion=0.20
        )

        prosodic = MagicMock()
        prosodic.analyze.return_value = MockProsodicFeatures(
            pause_ratio=0.15, jitter=0.03, pitch_std_hz=30.0
        )

        sentiment = MagicMock()
        sentiment.analyze.return_value = MagicMock(
            to_dict=lambda: {"label": "positive", "score": 0.85, "model_used": "mock"}
        )

        emotion = MagicMock()
        emotion.analyze.return_value = MagicMock(
            to_dict=lambda: {
                "emotions": {"joy": 0.7, "fear": 0.1, "sadness": 0.1, "anger": 0.1},
                "dominant": "joy",
                "dominant_score": 0.7,
                "model_used": "mock",
            }
        )

        return MultiChannelAnalyzer(
            transcriber=transcriber,
            linguistic_analyzer=linguistic,
            prosodic_analyzer=prosodic,
            sentiment_analyzer=sentiment,
            emotion_analyzer=emotion,
        )

    def _build_mci_analyzer(self):
        """Analyzer mockato per profilo MCI (indicatori peggiori)."""
        transcriber = MagicMock()
        transcriber.transcribe.return_value = MockTranscriptionResult(
            text="Ehm... non ricordo bene. Era... boh, credo tanto tempo fa."
        )

        linguistic = MagicMock()
        linguistic.analyze.return_value = MockLinguisticFeatures(
            word_count=15, mattr=0.40, lexical_density=0.30, cohesion=0.35
        )

        prosodic = MagicMock()
        prosodic.analyze.return_value = MockProsodicFeatures(
            pause_ratio=0.45, jitter=0.12, pitch_std_hz=12.0
        )

        sentiment = MagicMock()
        sentiment.analyze.return_value = MagicMock(
            to_dict=lambda: {"label": "negative", "score": 0.65, "model_used": "mock"}
        )

        emotion = MagicMock()
        emotion.analyze.return_value = MagicMock(
            to_dict=lambda: {
                "emotions": {"joy": 0.1, "fear": 0.3, "sadness": 0.5, "anger": 0.1},
                "dominant": "sadness",
                "dominant_score": 0.5,
                "model_used": "mock",
            }
        )

        return MultiChannelAnalyzer(
            transcriber=transcriber, linguistic_analyzer=linguistic,
            prosodic_analyzer=prosodic, sentiment_analyzer=sentiment,
            emotion_analyzer=emotion,
        )

    def test_healthy_profile_has_low_strain(self):
        """Un paziente sano deve avere cognitive strain basso."""
        analyzer = self._build_healthy_analyzer()
        result = analyzer.analyze_audio("mock.wav")

        assert "transcription" in result.channels_available
        assert "linguistic" in result.channels_available
        assert len(result.channels_available) == 5
        assert result.cognitive_strain_index < 40
        assert result.emotional_distress_index < 40
        assert result.communication_quality_index > 50

    def test_mci_profile_has_high_strain(self):
        """Un paziente MCI deve avere indicatori peggiori."""
        analyzer = self._build_mci_analyzer()
        result = analyzer.analyze_audio("mock.wav")

        assert result.cognitive_strain_index > 30  # strain rilevato
        assert result.emotional_distress_index > 30  # distress rilevato

    def test_healthy_vs_mci_comparison(self):
        """Confronto: MCI deve essere peggio del sano in tutti e 3 gli indici."""
        healthy = self._build_healthy_analyzer().analyze_audio("mock.wav")
        mci = self._build_mci_analyzer().analyze_audio("mock.wav")

        assert mci.cognitive_strain_index > healthy.cognitive_strain_index
        assert mci.emotional_distress_index > healthy.emotional_distress_index
        assert mci.communication_quality_index < healthy.communication_quality_index

    def test_graceful_degradation_no_audio(self):
        """Senza transcriber/prosodic, funziona solo analisi testuale."""
        analyzer = MultiChannelAnalyzer()
        result = analyzer.analyze_text("Oggi mi sento bene e sono felice.")
        assert result.transcript == "Oggi mi sento bene e sono felice."
        assert len(result.channels_available) == 0  # nessun modulo

    def test_text_analysis_with_sentiment_only(self):
        """Analisi di solo testo con solo sentiment disponibile."""
        sentiment = MagicMock()
        sentiment.analyze.return_value = MagicMock(
            to_dict=lambda: {"label": "negative", "score": 0.9, "model_used": "mock"}
        )
        analyzer = MultiChannelAnalyzer(sentiment_analyzer=sentiment)
        result = analyzer.analyze_text("Mi sento terribile.")
        assert "sentiment" in result.channels_available
        assert result.emotional_distress_index > 50
