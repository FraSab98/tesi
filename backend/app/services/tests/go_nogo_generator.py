"""
Generator per Go/No-Go Task.

Come per CPT, la generazione è principalmente procedurale perché riguarda
sequenze casuali con vincoli numerici. L'LLM può essere usato per variazioni
nei colori degli stimoli in base a profilo paziente (es. test per bambini
con colori più accattivanti), ma la struttura è algoritmica.
"""

import random
from typing import Type, List

from app.schemas.go_nogo import (
    GoNoGoConfig,
    GoNoGoTest,
    GoNoGoPhase,
    GoNoGoTrial,
)
from app.services.tests.base import TestGenerator


class GoNoGoGenerator(TestGenerator[GoNoGoConfig, GoNoGoTest]):
    """Generator per Go/No-Go Task."""

    @property
    def test_name(self) -> str:
        return "GoNoGo"

    @property
    def category(self) -> str:
        return "A"

    @property
    def output_schema(self) -> Type[GoNoGoTest]:
        return GoNoGoTest

    def default_temperature(self) -> float:
        return 0.2

    def build_system_prompt(self, config: GoNoGoConfig) -> str:
        return (
            "Sei un generatore di stimoli per Go/No-Go Task. "
            "Generi sequenze bilanciate e pseudo-casuali rispettando i vincoli "
            "di protocollo. Restituisci SOLO il JSON."
        )

    def build_user_prompt(self, config: GoNoGoConfig) -> str:
        # Placeholder: la generazione è principalmente procedurale
        return "Vedi override di generate()"

    async def generate(self, config: GoNoGoConfig) -> GoNoGoTest:
        """
        Override: generazione procedurale delle fasi.
        """
        phases = []

        # Fase 1: Formation (opzionale)
        if config.include_formation:
            formation = self._generate_formation_phase(config)
            phases.append(formation)

        # Fase 2: Differentiation
        differentiation = self._generate_differentiation_phase(config)
        phases.append(differentiation)

        # Fase 3: Reverse Differentiation (opzionale)
        if config.include_reverse:
            reverse = self._generate_reverse_phase(config)
            phases.append(reverse)

        return GoNoGoTest(phases=phases)

    def _generate_formation_phase(self, config: GoNoGoConfig) -> GoNoGoPhase:
        """5 trial solo Go per addestrare il paziente."""
        trials = [
            GoNoGoTrial(
                stimulus_type="go",
                stimulus_color=config.go_color,
                stimulus_duration_ms=self._random_duration(config),
                isi_ms=self._random_isi(config),
            )
            for _ in range(5)
        ]
        return GoNoGoPhase(
            phase="formation",
            go_stimulus_color=config.go_color,
            nogo_stimulus_color=config.nogo_color,
            trials=trials,
        )

    def _generate_differentiation_phase(self, config: GoNoGoConfig) -> GoNoGoPhase:
        """20 trial con 50% Go e 50% NoGo, pseudo-random."""
        return self._generate_balanced_phase(
            phase_name="differentiation",
            go_color=config.go_color,
            nogo_color=config.nogo_color,
            n_trials=config.trials_per_phase,
            config=config,
        )

    def _generate_reverse_phase(self, config: GoNoGoConfig) -> GoNoGoPhase:
        """Fase inversa: i colori Go/NoGo vengono scambiati."""
        return self._generate_balanced_phase(
            phase_name="reverse_differentiation",
            go_color=config.nogo_color,  # scambio
            nogo_color=config.go_color,  # scambio
            n_trials=config.trials_per_phase,
            config=config,
        )

    def _generate_balanced_phase(
        self,
        phase_name: str,
        go_color: str,
        nogo_color: str,
        n_trials: int,
        config: GoNoGoConfig,
    ) -> GoNoGoPhase:
        """Genera una fase con bilanciamento 50/50 e vincolo max 3 consecutivi."""
        n_go = n_trials // 2
        n_nogo = n_trials - n_go

        # Genera sequenza con vincolo: mai più di 3 dello stesso tipo
        types = self._shuffle_with_max_run(
            ["go"] * n_go + ["nogo"] * n_nogo,
            max_run=3,
        )

        trials = []
        for t in types:
            trials.append(GoNoGoTrial(
                stimulus_type=t,
                stimulus_color=go_color if t == "go" else nogo_color,
                stimulus_duration_ms=self._random_duration(config),
                isi_ms=self._random_isi(config),
            ))

        return GoNoGoPhase(
            phase=phase_name,
            go_stimulus_color=go_color,
            nogo_stimulus_color=nogo_color,
            trials=trials,
        )

    @staticmethod
    def _shuffle_with_max_run(items: List[str], max_run: int = 3) -> List[str]:
        """Shuffle evitando run più lunghe di max_run dello stesso elemento."""
        for _ in range(100):  # max 100 tentativi
            shuffled = items.copy()
            random.shuffle(shuffled)
            if GoNoGoGenerator._has_valid_runs(shuffled, max_run):
                return shuffled
        # Fallback: genera manualmente con backtracking semplice
        return GoNoGoGenerator._manual_balanced_shuffle(items, max_run)

    @staticmethod
    def _has_valid_runs(seq: List[str], max_run: int) -> bool:
        run = 1
        for i in range(1, len(seq)):
            if seq[i] == seq[i - 1]:
                run += 1
                if run > max_run:
                    return False
            else:
                run = 1
        return True

    @staticmethod
    def _manual_balanced_shuffle(items: List[str], max_run: int) -> List[str]:
        """Versione manuale che garantisce bilanciamento."""
        from collections import Counter
        counts = Counter(items)
        result = []
        prev = None
        run = 0

        while sum(counts.values()) > 0:
            # Scegli il tipo con più elementi rimasti, compatibile con il vincolo
            candidates = [k for k, v in counts.items() if v > 0]
            if prev and run >= max_run:
                candidates = [k for k in candidates if k != prev]
            if not candidates:
                candidates = [k for k, v in counts.items() if v > 0]

            # Preferisci il tipo più frequente rimanente (bilanciamento)
            chosen = max(candidates, key=lambda k: counts[k])
            result.append(chosen)
            counts[chosen] -= 1

            if chosen == prev:
                run += 1
            else:
                run = 1
            prev = chosen

        return result

    def _random_duration(self, config: GoNoGoConfig) -> int:
        return random.randint(
            config.stimulus_duration_min_ms,
            config.stimulus_duration_max_ms,
        )

    def _random_isi(self, config: GoNoGoConfig) -> int:
        return random.randint(config.isi_min_ms, config.isi_max_ms)
