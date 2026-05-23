"""
Unit test per i moduli di scoring.
"""

import pytest

from app.scoring.cpt_scorer import score_cpt, CPTResponse
from app.scoring.digit_span_scorer import score_digit_span, DigitSpanResponse
from app.scoring.stroop_scorer import score_stroop, StroopResponse
from app.scoring.go_nogo_scorer import score_go_nogo, GoNoGoResponse


class TestCPTScorer:
    def test_perfect_performance(self):
        """Paziente che risponde correttamente a tutto."""
        responses = [
            CPTResponse(i, "X" if i in {1, 3, 5} else "A",
                        is_target=i in {1, 3, 5},
                        responded=i in {1, 3, 5},
                        reaction_time_ms=450.0 if i in {1, 3, 5} else None)
            for i in range(10)
        ]
        score = score_cpt(responses)
        assert score.n_omissions == 0
        assert score.n_commissions == 0
        assert score.attention_score > 80

    def test_many_omissions(self):
        """Paziente che manca metà dei target."""
        responses = [
            CPTResponse(i, "X" if i in {1, 3, 5, 7} else "A",
                        is_target=i in {1, 3, 5, 7},
                        responded=i in {1, 5},  # manca 3 e 7
                        reaction_time_ms=500.0 if i in {1, 5} else None)
            for i in range(10)
        ]
        score = score_cpt(responses)
        assert score.n_omissions == 2
        assert score.omission_rate == 0.5


class TestDigitSpanScorer:
    def test_exact_match(self):
        """Risposta esatta = edit distance 0."""
        responses = [
            DigitSpanResponse(
                target_sequence=[3, 8, 1, 5],
                response_sequence=[3, 8, 1, 5],
                length=4,
            )
        ]
        score = score_digit_span(responses, mode="forward")
        assert score.n_exact == 1
        assert score.mean_edit_distance == 0
        assert score.fine_grained_score == 100.0

    def test_one_substitution(self):
        """Una sostituzione -> edit distance 1."""
        responses = [
            DigitSpanResponse(
                target_sequence=[3, 8, 1, 5],
                response_sequence=[3, 8, 2, 5],  # 1 -> 2
                length=4,
            )
        ]
        score = score_digit_span(responses, mode="forward")
        assert score.n_exact == 0
        assert score.total_substituted == 1
        assert score.mean_edit_distance == 1.0

    def test_missing_digit(self):
        """Cifra omessa -> deletion."""
        responses = [
            DigitSpanResponse(
                target_sequence=[3, 8, 1, 5],
                response_sequence=[3, 8, 5],  # manca 1
                length=4,
            )
        ]
        score = score_digit_span(responses, mode="forward")
        assert score.total_deleted == 1


class TestStroopScorer:
    def _mk_response(self, idx, ink, resp=None, rt=800):
        """Helper: crea una StroopResponse corretta o errata."""
        return StroopResponse(
            stimulus_index=idx,
            word="rosso",
            ink_color=ink,
            condition="incongruent",
            response_color=resp or ink,  # default: risposta corretta
            reaction_time_ms=rt,
            correct=(resp is None or resp == ink),
        )

    def test_perfect_blocks(self):
        word_block = [self._mk_response(i, "black") for i in range(5)]
        color_block = [self._mk_response(i, "rosso") for i in range(5)]
        cw_block = [self._mk_response(i, "blu") for i in range(5)]

        score = score_stroop(word_block, color_block, cw_block)
        assert score.block_scores["word"].accuracy == 1.0
        assert score.block_scores["color"].accuracy == 1.0
        assert score.block_scores["color_word"].accuracy == 1.0
        # Interference classic = C - CW (entrambi 5) = 0
        assert score.interference_classic == 0


class TestGoNoGoScorer:
    def test_risk_score_ranges(self):
        """Zero errori -> risk 0, alti errori -> risk alto."""
        # Paziente senza errori (10 Go + 10 NoGo tutti corretti)
        responses = []
        for i in range(20):
            is_go = i % 2 == 0
            responses.append(GoNoGoResponse(
                trial_index=i,
                phase="differentiation",
                stimulus_type="go" if is_go else "nogo",
                responded=is_go,  # risponde ai Go, non ai NoGo
                reaction_time_ms=450.0 if is_go else None,
            ))
        score = score_go_nogo(responses)
        assert score.total_error == 0
        assert score.screening_risk_score == 0

    def test_high_error_rate_flags_risk(self):
        """Paziente con molti errori deve avere risk alto."""
        responses = []
        # 10 Go tutti mancati, 10 NoGo con 5 errori
        for i in range(10):
            responses.append(GoNoGoResponse(
                trial_index=i,
                phase="differentiation",
                stimulus_type="go",
                responded=False,  # miss
                reaction_time_ms=None,
            ))
        for i in range(10, 20):
            responses.append(GoNoGoResponse(
                trial_index=i,
                phase="differentiation",
                stimulus_type="nogo",
                responded=(i < 15),  # 5 mistake
                reaction_time_ms=None,
            ))
        score = score_go_nogo(responses)
        assert score.total_miss == 10
        assert score.total_mistake == 5
        assert score.screening_risk_score > 50
