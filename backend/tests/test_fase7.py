"""
Unit test per Fase 7.
"""

from datetime import datetime, timedelta
import pytest

from app.reporting.aggregator import ReportAggregator, SessionReport
from app.longitudinal.analyzer import LongitudinalAnalyzer


# ==================== FIXTURE BUILDERS ====================

def make_patient(age=70, language="it", suspicion="MCI"):
    return {
        "external_code": "PAT001",
        "age": age,
        "language": language,
        "clinical_suspicion": suspicion,
    }


def make_session(id_="sess-1"):
    return {
        "id": id_,
        "clinician_id": "DR001",
        "created_at": datetime(2026, 1, 15, 10, 0),
    }


def make_cpt_score(attention_score=75, rt_var=0.15, omission_rate=0.08):
    return {
        "test_type": "CPT",
        "test_config_id": "cfg-cpt",
        "scores": {
            "attention_score": attention_score,
            "rt_variability": rt_var,
            "omission_rate": omission_rate,
            "n_targets": 40,
            "n_omissions": int(40 * omission_rate),
        },
    }


def make_digit_span_score(fine=75, longest=6):
    return {
        "test_type": "DigitSpan",
        "test_config_id": "cfg-ds",
        "scores": {
            "fine_grained_score": fine,
            "conventional_score": fine - 10,
            "longest_correct": longest,
            "mean_edit_distance": 1.2,
        },
    }


def make_gonogo_score(risk=35, total_error=3):
    return {
        "test_type": "GoNoGo",
        "test_config_id": "cfg-gng",
        "scores": {
            "screening_risk_score": risk,
            "total_error": total_error,
            "total_miss": 2,
            "total_mistake": 1,
            "overall_accuracy": 0.92,
        },
    }


# ==================== AGGREGATOR TESTS ====================

class TestReportAggregator:

    def test_healthy_profile_produces_low_risk(self):
        agg = ReportAggregator()
        report = agg.build_report(
            session=make_session(),
            patient=make_patient(age=40, suspicion=None),
            test_scores=[
                make_cpt_score(attention_score=88),
                make_digit_span_score(fine=85),
                make_gonogo_score(risk=20, total_error=1),
            ],
        )
        assert report.overall_cognitive_score > 70
        assert report.overall_risk_level == "low"
        # Nessun flag critico
        total_flags = sum(len(t.flags) for t in report.test_scores)
        assert total_flags <= 1

    def test_mci_profile_produces_high_risk(self):
        agg = ReportAggregator()
        report = agg.build_report(
            session=make_session(),
            patient=make_patient(age=78),
            test_scores=[
                make_cpt_score(attention_score=40, rt_var=0.40, omission_rate=0.25),
                make_digit_span_score(fine=55, longest=3),
                make_gonogo_score(risk=85, total_error=9),
            ],
        )
        assert report.overall_cognitive_score < 60
        assert report.overall_risk_level == "high"
        # Flags devono essere presenti
        total_flags = sum(len(t.flags) for t in report.test_scores)
        assert total_flags >= 3
        assert len(report.recommendations) > 0

    def test_adhd_pattern_triggers_specific_recommendation(self):
        agg = ReportAggregator()
        report = agg.build_report(
            session=make_session(),
            patient=make_patient(age=22, suspicion=None),
            test_scores=[
                make_cpt_score(attention_score=65, rt_var=0.45),  # alta variabilità
                make_digit_span_score(fine=78),
            ],
        )
        recs_text = " ".join(report.recommendations)
        assert "ADHD" in recs_text

    def test_multichannel_integration_flags_distress(self):
        agg = ReportAggregator()
        analyses = [
            {
                "cognitive_strain_index": 45,
                "emotional_distress_index": 75,
                "communication_quality_index": 40,
                "emotion": {"dominant": "sadness"},
            }
        ]
        report = agg.build_report(
            session=make_session(),
            patient=make_patient(),
            test_scores=[make_cpt_score(attention_score=70)],
            analysis_results=analyses,
        )
        assert report.multichannel is not None
        assert report.multichannel.avg_emotional_distress == 75
        findings_text = " ".join(report.key_findings)
        assert "distress" in findings_text.lower()
        recs_text = " ".join(report.recommendations)
        assert "psicologico" in recs_text.lower()


# ==================== LONGITUDINAL TESTS ====================

class TestLongitudinalAnalyzer:

    def _build_session_report(
        self, date: datetime, attention: float, fine: float
    ) -> dict:
        return {
            "session_id": f"sess-{date.isoformat()}",
            "session_date": date.isoformat(),
            "patient": {"code": "PAT001"},
            "test_scores": [
                {"test_type": "CPT", "scores": {
                    "attention_score": attention,
                    "rt_variability": 0.2,
                }},
                {"test_type": "DigitSpan", "scores": {
                    "fine_grained_score": fine,
                    "longest_correct": 6,
                }},
            ],
            "overall_cognitive_score": (attention + fine) / 2,
            "multichannel": None,
        }

    def test_improving_trend_detected(self):
        analyzer = LongitudinalAnalyzer()
        reports = [
            self._build_session_report(datetime(2025, 1, 1), 50, 50),
            self._build_session_report(datetime(2025, 4, 1), 65, 65),
            self._build_session_report(datetime(2025, 7, 1), 78, 78),
        ]
        result = analyzer.analyze_patient(reports)

        assert result.n_sessions == 3
        assert "overall_cognitive_score" in result.trends
        trend = result.trends["overall_cognitive_score"]
        assert trend.direction == "improving"
        assert trend.change_pct > 30  # da 50 a 78 = +56%
        assert trend.slope > 0

    def test_declining_trend_triggers_alert(self):
        analyzer = LongitudinalAnalyzer()
        reports = [
            self._build_session_report(datetime(2025, 1, 1), 85, 80),
            self._build_session_report(datetime(2025, 4, 1), 70, 70),
            self._build_session_report(datetime(2025, 7, 1), 55, 60),
            self._build_session_report(datetime(2025, 10, 1), 45, 50),
        ]
        result = analyzer.analyze_patient(reports)

        trend = result.trends["overall_cognitive_score"]
        assert trend.direction == "declining"
        assert trend.change_pct < -20
        # L'RCI dovrebbe essere >1.96 con 4 punti che mostrano trend forte
        assert len(result.alerts) > 0

    def test_stable_trend(self):
        analyzer = LongitudinalAnalyzer()
        reports = [
            self._build_session_report(datetime(2025, 1, 1), 75, 75),
            self._build_session_report(datetime(2025, 4, 1), 76, 74),
            self._build_session_report(datetime(2025, 7, 1), 74, 76),
        ]
        result = analyzer.analyze_patient(reports)

        trend = result.trends["overall_cognitive_score"]
        assert trend.direction == "stable"
        assert abs(trend.change_pct) < 10

    def test_single_session_returns_insufficient_data(self):
        analyzer = LongitudinalAnalyzer()
        reports = [self._build_session_report(datetime(2025, 1, 1), 70, 70)]
        result = analyzer.analyze_patient(reports)
        assert result.n_sessions == 1
        assert "insufficienti" in result.summary.lower()

    def test_span_days_computed(self):
        analyzer = LongitudinalAnalyzer()
        reports = [
            self._build_session_report(datetime(2025, 1, 1), 70, 70),
            self._build_session_report(datetime(2025, 7, 1), 65, 65),
        ]
        result = analyzer.analyze_patient(reports)
        assert 175 < result.span_days < 185  # circa 6 mesi
