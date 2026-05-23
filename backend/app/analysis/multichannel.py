"""
Pipeline di analisi multi-canale.

Questo è il modulo chiave della tesi: integra i tre canali di analisi
(timing/accuracy, linguaggio, prosodia+emozione) in un unico indicatore
cognitivo composito.

Nessuno dei paper dello stato dell'arte integra tutti e tre i canali:
- Paper 4 (CPT), 6 (Stroop), 9 (Go/No-Go): solo timing/accuracy
- Paper 5 (Digit Span Asgari), 11 (ADHD stilometria): timing + NLP
- Paper 1 (BPD), 2 (RMET stress): solo narrativa/emozione

L'integrazione multi-canale è il contributo originale della tesi.
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MultiChannelAnalysis:
    """Risultato dell'analisi completa multi-canale per una risposta vocale."""
    # Input
    audio_path: Optional[str] = None
    transcript: str = ""

    # Canale 1: Linguaggio
    linguistic: Optional[dict] = None

    # Canale 2: Prosodia
    prosodic: Optional[dict] = None

    # Canale 3: Sentiment/Emotion
    sentiment: Optional[dict] = None
    emotion: Optional[dict] = None

    # Indicatori compositi
    cognitive_strain_index: float = 0.0   # 0-100
    emotional_distress_index: float = 0.0  # 0-100
    communication_quality_index: float = 0.0  # 0-100

    # Metadata
    analysis_duration_s: float = 0.0
    channels_available: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class MultiChannelAnalyzer:
    """
    Orchestratore che combina trascrizione + linguistica + prosodia + emotion
    per produrre indicatori cognitivi compositi.

    Il design è graceful-degradation: se un modulo non è disponibile
    (es. librosa non installato), il canale corrispondente viene saltato
    ma l'analisi continua sugli altri.
    """

    def __init__(
        self,
        transcriber=None,
        linguistic_analyzer=None,
        prosodic_analyzer=None,
        sentiment_analyzer=None,
        emotion_analyzer=None,
        language: str = "it",
    ):
        self.transcriber = transcriber
        self.linguistic = linguistic_analyzer
        self.prosodic = prosodic_analyzer
        self.sentiment = sentiment_analyzer
        self.emotion = emotion_analyzer
        self.language = language

    def analyze_audio(
        self,
        audio_path: str,
        initial_prompt: Optional[str] = None,
    ) -> MultiChannelAnalysis:
        """
        Analisi completa di un audio: trascrizione + linguistica + prosodia + emotion.
        """
        import time
        start = time.perf_counter()

        result = MultiChannelAnalysis(audio_path=audio_path)
        channels = []

        # ============ Canale 1: Trascrizione + Linguistica ============
        transcript = ""
        if self.transcriber is not None:
            try:
                trans_result = self.transcriber.transcribe(
                    audio_path,
                    language=self.language,
                    initial_prompt=initial_prompt,
                )
                transcript = trans_result.text
                result.transcript = transcript
                channels.append("transcription")
            except Exception as e:
                logger.error(f"Errore trascrizione: {e}")

        if transcript and self.linguistic is not None:
            try:
                ling = self.linguistic.analyze(transcript)
                result.linguistic = ling.to_dict()
                channels.append("linguistic")
            except Exception as e:
                logger.error(f"Errore analisi linguistica: {e}")

        # ============ Canale 2: Prosodia ============
        if self.prosodic is not None:
            try:
                pros = self.prosodic.analyze(audio_path)
                result.prosodic = pros.to_dict()
                channels.append("prosodic")
            except Exception as e:
                logger.error(f"Errore analisi prosodica: {e}")

        # ============ Canale 3: Sentiment + Emotion ============
        if transcript and self.sentiment is not None:
            try:
                sent = self.sentiment.analyze(transcript)
                result.sentiment = sent.to_dict()
                channels.append("sentiment")
            except Exception as e:
                logger.error(f"Errore sentiment: {e}")

        if transcript and self.emotion is not None:
            try:
                emo = self.emotion.analyze(transcript)
                result.emotion = emo.to_dict()
                channels.append("emotion")
            except Exception as e:
                logger.error(f"Errore emotion: {e}")

        # ============ Indicatori compositi ============
        result.cognitive_strain_index = self._compute_cognitive_strain(result)
        result.emotional_distress_index = self._compute_emotional_distress(result)
        result.communication_quality_index = self._compute_communication_quality(result)

        result.channels_available = channels
        result.analysis_duration_s = time.perf_counter() - start

        return result

    def analyze_text(self, text: str) -> MultiChannelAnalysis:
        """Analisi di solo testo (senza audio): linguistica + sentiment + emotion."""
        import time
        start = time.perf_counter()

        result = MultiChannelAnalysis(transcript=text)
        channels = []

        if self.linguistic is not None:
            try:
                ling = self.linguistic.analyze(text)
                result.linguistic = ling.to_dict()
                channels.append("linguistic")
            except Exception as e:
                logger.error(f"Errore linguistica: {e}")

        if self.sentiment is not None:
            try:
                sent = self.sentiment.analyze(text)
                result.sentiment = sent.to_dict()
                channels.append("sentiment")
            except Exception as e:
                logger.error(f"Errore sentiment: {e}")

        if self.emotion is not None:
            try:
                emo = self.emotion.analyze(text)
                result.emotion = emo.to_dict()
                channels.append("emotion")
            except Exception as e:
                logger.error(f"Errore emotion: {e}")

        result.cognitive_strain_index = self._compute_cognitive_strain(result)
        result.emotional_distress_index = self._compute_emotional_distress(result)
        result.communication_quality_index = self._compute_communication_quality(result)

        result.channels_available = channels
        result.analysis_duration_s = time.perf_counter() - start

        return result

    # ========================================================
    # INDICATORI COMPOSITI
    # Ognuno combina segnali da più canali per produrre un
    # punteggio 0-100 interpretabile dal medico.
    # ========================================================

    @staticmethod
    def _compute_cognitive_strain(r: MultiChannelAnalysis) -> float:
        """
        Cognitive Strain Index: 0 (nessuno sforzo) a 100 (alto sforzo cognitivo).

        Segnali integrati:
        - Linguistica: bassa densità/diversità lessicale → strain alto
          (Paper 11: pazienti ADHD hanno narrazioni più brevi e meno dense)
        - Prosodia: pause frequenti, velocità ridotta → strain alto
        - Prosodia: jitter/shimmer alti → affaticamento vocale
        """
        score = 0.0
        n_signals = 0

        if r.linguistic:
            ling = r.linguistic
            # Densità lessicale bassa (< 0.5) indica difficoltà
            density = ling.get("lexical_density", 0.5)
            if density > 0:
                strain_density = max(0, (0.5 - density) * 100)
                score += strain_density
                n_signals += 1

            # MATTR basso (< 0.6) indica vocabolario ridotto
            mattr = ling.get("mattr", 0.6)
            if mattr > 0:
                strain_mattr = max(0, (0.6 - mattr) * 100)
                score += strain_mattr
                n_signals += 1

        if r.prosodic:
            pros = r.prosodic
            # Pause > 30% del tempo → strain alto
            pause_ratio = pros.get("pause_ratio", 0)
            strain_pause = min(100, pause_ratio * 200)
            score += strain_pause
            n_signals += 1

            # Jitter alto → stress vocale
            jitter = pros.get("jitter", 0)
            strain_jitter = min(100, jitter * 500)
            score += strain_jitter
            n_signals += 1

        return score / n_signals if n_signals else 0.0

    @staticmethod
    def _compute_emotional_distress(r: MultiChannelAnalysis) -> float:
        """
        Emotional Distress Index: 0 (sereno) a 100 (distress alto).

        Segnali:
        - Sentiment negativo
        - Emozioni negative dominanti (fear, sadness, anger)
        - Prosodia: pitch molto variabile o molto ristretto
        """
        score = 0.0
        n_signals = 0

        if r.sentiment:
            if r.sentiment.get("label") == "negative":
                score += r.sentiment.get("score", 0) * 100
                n_signals += 1
            elif r.sentiment.get("label") == "positive":
                # Riduce il distress
                score += (1 - r.sentiment.get("score", 0)) * 50
                n_signals += 1

        if r.emotion:
            emotions = r.emotion.get("emotions", {})
            negative_emotions = ["fear", "sadness", "anger", "disgust",
                                 "paura", "tristezza", "rabbia"]
            neg_score = sum(
                emotions.get(e, 0) for e in negative_emotions
            )
            score += min(100, neg_score * 100)
            n_signals += 1

        if r.prosodic:
            pros = r.prosodic
            pitch_std = pros.get("pitch_std_hz", 0)
            # Pitch std molto alto o molto basso è anomalo
            # Normal: 20-60 Hz. > 100 o < 10 → anomalo
            if pitch_std > 100:
                score += min(100, (pitch_std - 60) * 0.5)
                n_signals += 1
            elif 0 < pitch_std < 10:
                score += 40  # monotono
                n_signals += 1

        return score / n_signals if n_signals else 0.0

    @staticmethod
    def _compute_communication_quality(r: MultiChannelAnalysis) -> float:
        """
        Communication Quality Index: 0 (comunicazione compromessa) a 100 (ottima).

        Segnali positivi:
        - Alta coesione narrativa
        - Diversità lessicale alta
        - Velocità appropriata
        - Pause moderate (non eccessive)
        """
        if not r.linguistic and not r.prosodic:
            return 0.0

        score = 50.0  # baseline neutro
        signals = 0

        if r.linguistic:
            ling = r.linguistic
            # Coesione tra 15% e 30% è ottimale per italiano
            cohesion = ling.get("cohesion", 0.2)
            if 0.15 <= cohesion <= 0.30:
                score += 15
            else:
                score -= abs(cohesion - 0.225) * 100
            signals += 1

            # MATTR alto è buono
            mattr = ling.get("mattr", 0.6)
            score += (mattr - 0.5) * 50
            signals += 1

        if r.prosodic:
            pros = r.prosodic
            # Pause_ratio tra 10% e 25% è ottimale
            pause_ratio = pros.get("pause_ratio", 0.15)
            if 0.10 <= pause_ratio <= 0.25:
                score += 10
            else:
                score -= abs(pause_ratio - 0.175) * 100
            signals += 1

        return max(0, min(100, score))
