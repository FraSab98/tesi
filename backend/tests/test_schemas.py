"""
Unit test per gli schemi Pydantic.
Verificano che i vincoli di validazione funzionino correttamente.

Esecuzione: pytest tests/test_schemas.py -v
"""

import pytest
from pydantic import ValidationError

from app.schemas.cpt import CPTStimulus, CPTSequence, CPTConfig
from app.schemas.digit_span import DigitSpanSequence, DigitSpanBatch, DigitSpanConfig
from app.schemas.stroop import StroopStimulus, StroopBlock, StroopConfig
from app.schemas.go_nogo import GoNoGoTrial, GoNoGoPhase, GoNoGoTest, GoNoGoConfig


# ============ CPT ============

class TestCPTSchemas:
    def test_valid_cpt_sequence(self):
        """Una sequenza CPT valida con target e distrattori."""
        seq = CPTSequence(
            target_letter="X",
            stimuli=[
                CPTStimulus(stimulus="A", is_target=False, isi_ms=1500),
                CPTStimulus(stimulus="X", is_target=True, isi_ms=2000),
                CPTStimulus(stimulus="K", is_target=False, isi_ms=1200),
                CPTStimulus(stimulus="M", is_target=False, isi_ms=1800),
                CPTStimulus(stimulus="X", is_target=True, isi_ms=2500),
                CPTStimulus(stimulus="B", is_target=False, isi_ms=1500),
                CPTStimulus(stimulus="C", is_target=False, isi_ms=1300),
                CPTStimulus(stimulus="X", is_target=True, isi_ms=2100),
                CPTStimulus(stimulus="D", is_target=False, isi_ms=1600),
                CPTStimulus(stimulus="E", is_target=False, isi_ms=1400),
            ],
        )
        assert len(seq.stimuli) == 10
        assert sum(1 for s in seq.stimuli if s.is_target) == 3

    def test_too_many_consecutive_targets_rejected(self):
        """4 target consecutivi devono essere rifiutati."""
        with pytest.raises(ValidationError, match="3 target consecutivi"):
            CPTSequence(
                target_letter="X",
                stimuli=[
                    CPTStimulus(stimulus="A", is_target=False, isi_ms=1500),
                    CPTStimulus(stimulus="X", is_target=True, isi_ms=1500),
                    CPTStimulus(stimulus="X", is_target=True, isi_ms=1500),
                    CPTStimulus(stimulus="X", is_target=True, isi_ms=1500),
                    CPTStimulus(stimulus="X", is_target=True, isi_ms=1500),  # 4 consecutivi!
                    CPTStimulus(stimulus="B", is_target=False, isi_ms=1500),
                    CPTStimulus(stimulus="C", is_target=False, isi_ms=1500),
                    CPTStimulus(stimulus="D", is_target=False, isi_ms=1500),
                    CPTStimulus(stimulus="E", is_target=False, isi_ms=1500),
                    CPTStimulus(stimulus="F", is_target=False, isi_ms=1500),
                ],
            )

    def test_target_mismatch_rejected(self):
        """Uno stimolo marcato come target ma con lettera diversa è rifiutato."""
        with pytest.raises(ValidationError):
            CPTSequence(
                target_letter="X",
                stimuli=[
                    CPTStimulus(stimulus="A", is_target=True, isi_ms=1500),  # A come target?!
                ] * 10,
            )

    def test_config_total_stimuli_calculation(self):
        cfg = CPTConfig(
            total_duration_minutes=10,
            stimulus_duration_ms=250,
            isi_min_ms=1000,
            isi_max_ms=3000,
        )
        n = cfg.total_stimuli_count()
        # 10min = 600000ms; ISI medio 2000 + stim 250 = 2250ms per stimolo
        # ~ 266 stimoli
        assert 200 < n < 300


# ============ DIGIT SPAN ============

class TestDigitSpanSchemas:
    def test_valid_sequence(self):
        seq = DigitSpanSequence(sequence=[3, 8, 1, 5], length=4)
        assert len(seq.sequence) == 4

    def test_rejects_zero(self):
        with pytest.raises(ValidationError):
            DigitSpanSequence(sequence=[3, 0, 1, 5], length=4)

    def test_rejects_consecutive_duplicates(self):
        with pytest.raises(ValidationError, match="identiche consecutive"):
            DigitSpanSequence(sequence=[3, 3, 1, 5], length=4)

    def test_rejects_arithmetic_progression(self):
        with pytest.raises(ValidationError, match="Progressione aritmetica"):
            DigitSpanSequence(sequence=[1, 2, 3, 7], length=4)

    def test_rejects_length_mismatch(self):
        with pytest.raises(ValidationError, match="length"):
            DigitSpanSequence(sequence=[3, 8, 1], length=5)

    def test_batch_same_length(self):
        """Tutte le sequenze del batch devono avere lunghezza uguale."""
        with pytest.raises(ValidationError, match="lunghezze diverse"):
            DigitSpanBatch(
                mode="forward",
                sequences=[
                    DigitSpanSequence(sequence=[3, 8, 1], length=3),
                    DigitSpanSequence(sequence=[7, 2, 9, 4], length=4),
                ],
            )

    def test_config_backward_max_length(self):
        with pytest.raises(ValidationError):
            DigitSpanConfig(mode="backward", max_length=9)


# ============ STROOP ============

class TestStroopSchemas:
    def test_incongruent_stimulus(self):
        s = StroopStimulus(word="rosso", ink_color="blu", condition="incongruent")
        assert s.word.lower() != s.ink_color.lower()

    def test_congruent_mismatch_rejected(self):
        """Condizione congruent ma parola != colore -> errore."""
        with pytest.raises(ValidationError):
            StroopStimulus(word="rosso", ink_color="blu", condition="congruent")

    def test_incongruent_match_rejected(self):
        """Condizione incongruent ma parola == colore -> errore."""
        with pytest.raises(ValidationError):
            StroopStimulus(word="rosso", ink_color="rosso", condition="incongruent")

    def test_block_requires_incongruent_majority(self):
        """Blocco color_word deve avere >=70% incongruenti."""
        with pytest.raises(ValidationError, match="70%"):
            StroopBlock(
                condition="color_word",
                language="it",
                stimuli=[StroopStimulus(
                    word="xxx", ink_color="rosso", condition="neutral"
                )] * 10,
            )


# ============ GO/NO-GO ============

class TestGoNoGoSchemas:
    def _valid_trial(self, stim_type="go", color="red"):
        return GoNoGoTrial(
            stimulus_type=stim_type,
            stimulus_color=color,
            stimulus_duration_ms=500,
            isi_ms=2000,
        )

    def test_valid_differentiation_phase(self):
        trials = []
        # alternati 10 go + 10 nogo
        for i in range(20):
            t = "go" if i % 2 == 0 else "nogo"
            color = "red" if t == "go" else "yellow"
            trials.append(self._valid_trial(t, color))

        phase = GoNoGoPhase(
            phase="differentiation",
            go_stimulus_color="red",
            nogo_stimulus_color="yellow",
            trials=trials,
        )
        assert len(phase.trials) == 20

    def test_formation_only_go(self):
        """Formation phase può contenere solo Go."""
        with pytest.raises(ValidationError, match="solo stimoli Go"):
            GoNoGoPhase(
                phase="formation",
                go_stimulus_color="red",
                nogo_stimulus_color="yellow",
                trials=[self._valid_trial("nogo", "yellow")] * 5,
            )

    def test_reverse_phase_needs_swapped_colors(self):
        """La reverse phase deve avere Go/NoGo invertiti."""
        # Formation: solo go
        formation_trials = [self._valid_trial("go", "red") for _ in range(5)]

        # Differentiation: alternati go/nogo
        diff_trials = []
        for i in range(20):
            t = "go" if i % 2 == 0 else "nogo"
            color = "red" if t == "go" else "yellow"
            diff_trials.append(self._valid_trial(t, color))

        # Reverse trials con colori sbagliati (non invertiti)
        rev_trials = []
        for i in range(20):
            t = "go" if i % 2 == 0 else "nogo"
            # SBAGLIATO: usa gli stessi colori invece di invertirli
            color = "red" if t == "go" else "yellow"
            rev_trials.append(self._valid_trial(t, color))

        # Reverse con gli stessi colori (sbagliato!)
        with pytest.raises(ValidationError, match="invertiti"):
            GoNoGoTest(phases=[
                GoNoGoPhase(
                    phase="formation",
                    go_stimulus_color="red",
                    nogo_stimulus_color="yellow",
                    trials=formation_trials,
                ),
                GoNoGoPhase(
                    phase="differentiation",
                    go_stimulus_color="red",
                    nogo_stimulus_color="yellow",
                    trials=diff_trials,
                ),
                GoNoGoPhase(
                    phase="reverse_differentiation",
                    go_stimulus_color="red",  # dovrebbe essere yellow!
                    nogo_stimulus_color="yellow",
                    trials=rev_trials,
                ),
            ])
