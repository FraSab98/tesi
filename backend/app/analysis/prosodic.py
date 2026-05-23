"""
Analisi prosodica del parlato con librosa.

Estrae feature prosodiche che riflettono lo stato emotivo e cognitivo:
- Pitch (F0): tono fondamentale della voce
- Energia (RMS): volume
- Velocità del parlato: zero-crossing rate come proxy
- Jitter/Shimmer: microvariazioni di frequenza/ampiezza (stress vocale)
- MFCC: coefficienti standard per speech emotion recognition
- Pause: rapporto silenzio/parlato

Queste feature sono utili per:
- Rilevare affaticamento cognitivo (velocità ↓, pause ↑)
- Rilevare ansia/stress (jitter ↑, pitch variability ↑)
- Rilevare depressione (energia ↓, pitch range ristretto)
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


@dataclass
class ProsodicFeatures:
    """Feature prosodiche estratte da un audio."""
    duration_s: float
    # Pitch (F0)
    mean_pitch_hz: float
    pitch_std_hz: float
    pitch_range_hz: float
    # Energia
    mean_energy: float
    energy_std: float
    # Velocità e ritmo
    speech_rate_proxy: float   # zero-crossing rate medio
    pause_ratio: float         # frazione di tempo in silenzio
    n_pauses: int
    # Qualità vocale
    jitter: float              # variazione della frequenza
    shimmer: float             # variazione dell'ampiezza
    # MFCC (primi 13 coefficienti, media e std)
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
            "mfcc_mean": [round(x, 3) for x in self.mfcc_mean],
            "mfcc_std": [round(x, 3) for x in self.mfcc_std],
        }


class ProsodicAnalyzer:
    """Estrae feature prosodiche da file audio."""

    def __init__(self, sample_rate: int = 16000):
        if not _LIBROSA_AVAILABLE:
            raise ImportError(
                "librosa non installato. "
                "Installa con: pip install librosa"
            )
        self.sample_rate = sample_rate

    def analyze(self, audio_path: str) -> ProsodicFeatures:
        """Estrae feature prosodiche da un file audio."""
        y, sr = librosa.load(audio_path, sr=self.sample_rate)
        duration = len(y) / sr

        if duration < 0.1:
            logger.warning(f"Audio troppo breve ({duration:.2f}s), feature inaffidabili")

        # ============ PITCH (F0) ============
        # piptrack estrae pitch frame-by-frame
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr, threshold=0.1)
        # Per ogni frame prendiamo il pitch con magnitudine massima
        pitch_values = []
        for t in range(pitches.shape[1]):
            idx = magnitudes[:, t].argmax()
            p = pitches[idx, t]
            if p > 50 and p < 500:  # range vocale umano
                pitch_values.append(p)

        pitch_values = np.array(pitch_values) if pitch_values else np.array([0.0])
        mean_pitch = float(np.mean(pitch_values))
        pitch_std = float(np.std(pitch_values))
        pitch_range = float(np.max(pitch_values) - np.min(pitch_values))

        # ============ ENERGIA (RMS) ============
        rms = librosa.feature.rms(y=y)[0]
        mean_energy = float(np.mean(rms))
        energy_std = float(np.std(rms))

        # ============ VELOCITÀ PARLATO ============
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        speech_rate = float(np.mean(zcr))

        # ============ PAUSE ============
        # Silenzio = frame con RMS sotto soglia (20% della media)
        threshold = mean_energy * 0.2
        silent_frames = rms < threshold
        pause_ratio = float(np.mean(silent_frames))

        # Conta pause contigue (run di silent_frames)
        n_pauses = 0
        in_pause = False
        min_pause_frames = int(0.3 * sr / 512)  # 300ms minimo per essere una "pausa"
        run = 0
        for is_silent in silent_frames:
            if is_silent:
                run += 1
                if run >= min_pause_frames and not in_pause:
                    n_pauses += 1
                    in_pause = True
            else:
                run = 0
                in_pause = False

        # ============ JITTER & SHIMMER (semplificati) ============
        # Jitter: variazione relativa tra pitch consecutivi
        if len(pitch_values) > 1:
            pitch_diffs = np.abs(np.diff(pitch_values))
            jitter = float(np.mean(pitch_diffs) / mean_pitch) if mean_pitch > 0 else 0.0
        else:
            jitter = 0.0

        # Shimmer: variazione relativa tra ampiezze consecutive
        if len(rms) > 1:
            rms_diffs = np.abs(np.diff(rms))
            shimmer = float(np.mean(rms_diffs) / mean_energy) if mean_energy > 0 else 0.0
        else:
            shimmer = 0.0

        # ============ MFCC ============
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = mfcc.mean(axis=1).tolist()
        mfcc_std = mfcc.std(axis=1).tolist()

        return ProsodicFeatures(
            duration_s=duration,
            mean_pitch_hz=mean_pitch,
            pitch_std_hz=pitch_std,
            pitch_range_hz=pitch_range,
            mean_energy=mean_energy,
            energy_std=energy_std,
            speech_rate_proxy=speech_rate,
            pause_ratio=pause_ratio,
            n_pauses=n_pauses,
            jitter=jitter,
            shimmer=shimmer,
            mfcc_mean=mfcc_mean,
            mfcc_std=mfcc_std,
        )
