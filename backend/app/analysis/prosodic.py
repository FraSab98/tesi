"""
Analisi prosodica del parlato.

Strategia ibrida (valida clinicamente):
- librosa  -> ritmo, pause, energia, pitch globale, MFCC
- Parselmouth/Praat -> qualita vocale CLINICA: jitter (local), shimmer (local),
  HNR (Harmonics-to-Noise Ratio), misurati sui cicli glottali (PointProcess),
  non come approssimazione frame-by-frame.

Perche Praat: jitter e shimmer clinici si definiscono come perturbazioni
ciclo-a-ciclo dei singoli impulsi glottali. Praat e lo standard mondiale della
fonetica clinica; usarlo da' validita ai dati per Parkinson, Alzheimer, ecc.

Se Parselmouth non e installato, il modulo ripiega sull'approssimazione librosa
(campo voice_quality_method = "librosa_proxy") cosi il sistema non si rompe mai.

NOTA METODOLOGICA: jitter/shimmer/HNR sono piu affidabili su segmenti VOCALIZZATI
e, idealmente, su una VOCALE SOSTENUTA (/aaa/). Sul parlato spontaneo restano
indicativi (Praat li calcola sui frame voiced) ma piu rumorosi: per misure
"da manuale" si affianca un breve task di fonazione sostenuta.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import librosa
    import numpy as np
    _LIBROSA_AVAILABLE = True
except ImportError:
    _LIBROSA_AVAILABLE = False

try:
    import parselmouth
    from parselmouth.praat import call as _praat_call
    _PARSELMOUTH_AVAILABLE = True
except ImportError:
    _PARSELMOUTH_AVAILABLE = False


@dataclass
class ProsodicFeatures:
    """Feature prosodiche estratte da un audio."""
    duration_s: float
    mean_pitch_hz: float
    pitch_std_hz: float
    pitch_range_hz: float
    mean_energy: float
    energy_std: float
    speech_rate_proxy: float
    pause_ratio: float
    n_pauses: int
    # --- Qualita vocale ---
    # jitter/shimmer mantenuti per compatibilita a valle (ora popolati con i
    # valori Praat se disponibili, altrimenti col proxy librosa).
    jitter: float
    shimmer: float
    # --- Misure cliniche Praat (nuove, esplicite) ---
    jitter_local: Optional[float] = None    # perturbazione di periodo (frazione)
    shimmer_local: Optional[float] = None   # perturbazione di ampiezza (frazione)
    hnr_db: Optional[float] = None          # Harmonics-to-Noise Ratio in dB
    voice_quality_method: str = "librosa_proxy"  # "praat" | "librosa_proxy"
    mfcc_mean: list = field(default_factory=list)
    mfcc_std: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "duration_s": round(self.duration_s, 2),
            "mean_pitch_hz": round(self.mean_pitch_hz, 2),
            "pitch_std_hz": round(self.pitch_std_hz, 2),
            "pitch_range_hz": round(self.pitch_range_hz, 2),
            "mean_energy": round(self.mean_energy, 6),
            "energy_std": round(self.energy_std, 6),
            "speech_rate_proxy": round(self.speech_rate_proxy, 4),
            "pause_ratio": round(self.pause_ratio, 4),
            "n_pauses": self.n_pauses,
            "jitter": round(self.jitter, 6),
            "shimmer": round(self.shimmer, 6),
            "jitter_local": round(self.jitter_local, 6) if self.jitter_local is not None else None,
            "shimmer_local": round(self.shimmer_local, 6) if self.shimmer_local is not None else None,
            "hnr_db": round(self.hnr_db, 2) if self.hnr_db is not None else None,
            "voice_quality_method": self.voice_quality_method,
            "mfcc_mean": [round(x, 3) for x in self.mfcc_mean],
            "mfcc_std": [round(x, 3) for x in self.mfcc_std],
        }


def _voice_quality_praat(y, sr, f0min: float = 75.0, f0max: float = 500.0):
    """
    Calcola (jitter_local, shimmer_local, hnr_db) con Praat via Parselmouth,
    partendo direttamente dai campioni (niente problemi di formato file).
    Ritorna None se Parselmouth non e disponibile o il calcolo fallisce.
    """
    if not _PARSELMOUTH_AVAILABLE:
        return None
    try:
        snd = parselmouth.Sound(y.astype("float64"), sampling_frequency=sr)
        # PointProcess periodico (cicli glottali) -> base per jitter/shimmer
        pp = _praat_call(snd, "To PointProcess (periodic, cc)", f0min, f0max)
        jitter_local = _praat_call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        shimmer_local = _praat_call([snd, pp], "Get shimmer (local)",
                                    0, 0, 0.0001, 0.02, 1.3, 1.6)
        # HNR
        harm = _praat_call(snd, "To Harmonicity (cc)", 0.01, f0min, 0.1, 1.0)
        hnr_db = _praat_call(harm, "Get mean", 0, 0)

        # Praat restituisce NaN se non trova abbastanza cicli voiced
        import math
        if any(isinstance(v, float) and math.isnan(v) for v in (jitter_local, shimmer_local, hnr_db)):
            logger.info("Praat: segmento poco vocalizzato, misure non affidabili")
            return None
        return float(jitter_local), float(shimmer_local), float(hnr_db)
    except Exception as e:
        logger.warning(f"Calcolo Praat fallito, uso proxy librosa: {e}")
        return None


class ProsodicAnalyzer:
    """Estrae feature prosodiche da file audio."""

    def __init__(self, sample_rate: int = 16000):
        if not _LIBROSA_AVAILABLE:
            raise ImportError("librosa non installato. Installa con: pip install librosa")
        self.sample_rate = sample_rate

    def analyze(self, audio_path: str) -> ProsodicFeatures:
        y, sr = librosa.load(audio_path, sr=self.sample_rate)
        duration = len(y) / sr
        if duration < 0.1:
            logger.warning(f"Audio troppo breve ({duration:.2f}s), feature inaffidabili")

        # ---- Pitch (F0) con librosa ----
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr, threshold=0.1)
        pitch_values = []
        for t in range(pitches.shape[1]):
            idx = magnitudes[:, t].argmax()
            p = pitches[idx, t]
            if 50 < p < 500:
                pitch_values.append(p)
        pitch_values = np.array(pitch_values) if pitch_values else np.array([0.0])
        mean_pitch = float(np.mean(pitch_values))
        pitch_std = float(np.std(pitch_values))
        pitch_range = float(np.max(pitch_values) - np.min(pitch_values))

        # ---- Energia (RMS) ----
        rms = librosa.feature.rms(y=y)[0]
        mean_energy = float(np.mean(rms))
        energy_std = float(np.std(rms))

        # ---- Velocita parlato ----
        speech_rate = float(np.mean(librosa.feature.zero_crossing_rate(y)[0]))

        # ---- Pause ----
        threshold = mean_energy * 0.2
        silent_frames = rms < threshold
        pause_ratio = float(np.mean(silent_frames))
        n_pauses, in_pause, run = 0, False, 0
        min_pause_frames = int(0.3 * sr / 512)
        for is_silent in silent_frames:
            if is_silent:
                run += 1
                if run >= min_pause_frames and not in_pause:
                    n_pauses += 1; in_pause = True
            else:
                run = 0; in_pause = False

        # ---- Qualita vocale: PRAAT se possibile, altrimenti proxy librosa ----
        praat = _voice_quality_praat(y, sr)
        if praat is not None:
            jitter_local, shimmer_local, hnr_db = praat
            jitter, shimmer = jitter_local, shimmer_local  # compat. a valle
            method = "praat"
        else:
            # proxy (vecchio metodo): variazione relativa frame-by-frame
            if len(pitch_values) > 1 and mean_pitch > 0:
                jitter = float(np.mean(np.abs(np.diff(pitch_values))) / mean_pitch)
            else:
                jitter = 0.0
            if len(rms) > 1 and mean_energy > 0:
                shimmer = float(np.mean(np.abs(np.diff(rms))) / mean_energy)
            else:
                shimmer = 0.0
            jitter_local = shimmer_local = hnr_db = None
            method = "librosa_proxy"

        # ---- MFCC ----
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

        return ProsodicFeatures(
            duration_s=duration,
            mean_pitch_hz=mean_pitch, pitch_std_hz=pitch_std, pitch_range_hz=pitch_range,
            mean_energy=mean_energy, energy_std=energy_std,
            speech_rate_proxy=speech_rate, pause_ratio=pause_ratio, n_pauses=n_pauses,
            jitter=jitter, shimmer=shimmer,
            jitter_local=jitter_local, shimmer_local=shimmer_local, hnr_db=hnr_db,
            voice_quality_method=method,
            mfcc_mean=mfcc.mean(axis=1).tolist(), mfcc_std=mfcc.std(axis=1).tolist(),
        )
