"""
Analisi longitudinale: confronto tra sessioni successive dello stesso paziente.

Il caso d'uso principale è il monitoraggio di pazienti con MCI o a rischio:
sessioni trimestrali/semestrali permettono di rilevare trend di declino
(o miglioramento dopo terapia) che una singola sessione non può evidenziare.

Metriche chiave:
- Trend direction per ogni indicatore (improving, stable, declining)
- Reliable Change Index (RCI) come in Paper 10 (Zegers 2023)
- Visualizzazione slope di regressione lineare
- Alert automatici su declini significativi
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import math

logger = logging.getLogger(__name__)


@dataclass
class MetricTrend:
    """Trend di una singola metrica nel tempo."""
    metric_name: str
    values: list[float]
    dates: list[str]
    # Trend analysis
    slope: float                   # regressione lineare
    direction: str                 # improving | stable | declining
    change_pct: float              # % di variazione tra prima e ultima
    reliable_change: bool          # se il cambiamento è "reliable" (RCI)
    rci_value: float               # Reliable Change Index

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LongitudinalReport:
    """Report longitudinale completo per un paziente."""
    patient_code: str
    n_sessions: int
    first_session_date: Optional[str]
    last_session_date: Optional[str]
    span_days: int

    # Trend per ogni metrica
    trends: dict[str, MetricTrend] = field(default_factory=dict)

    # Alert clinici
    alerts: list[str] = field(default_factory=list)

    # Sintesi testuale
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "patient_code": self.patient_code,
            "n_sessions": self.n_sessions,
            "first_session_date": self.first_session_date,
            "last_session_date": self.last_session_date,
            "span_days": self.span_days,
            "trends": {k: v.to_dict() for k, v in self.trends.items()},
            "alerts": self.alerts,
            "summary": self.summary,
        }


class LongitudinalAnalyzer:
    """
    Analizza sessioni multiple di un paziente per identificare trend.

    Metriche tracciate:
    - overall_cognitive_score (media test)
    - Per ogni test: metrica chiave (attention_score, fine_grained, etc.)
    - Indicatori multi-canale: strain, distress, quality
    """

    # Parametri statistici
    RCI_CRITICAL = 1.96  # soglia RCI per cambiamento significativo (95%)
    SLOPE_STABLE_THRESHOLD = 0.5  # slope tra -0.5 e 0.5 = stabile

    # Indicatori in cui un aumento è MIGLIORE
    HIGHER_IS_BETTER = {
        "overall_cognitive_score",
        "attention_score", "fine_grained_score", "conventional_score",
        "overall_accuracy", "communication_quality",
        "cw_accuracy",
    }

    # Indicatori in cui un aumento è PEGGIORE
    LOWER_IS_BETTER = {
        "rt_variability", "omission_rate", "commission_rate",
        "screening_risk_score", "total_error",
        "cognitive_strain", "emotional_distress",
        "interference_rt_ms",
    }

    def analyze_patient(self, reports: list[dict]) -> LongitudinalReport:
        """
        Analizza una lista di report ordinati cronologicamente.

        Args:
            reports: lista di dict con struttura SessionReport.to_dict()

        Returns:
            LongitudinalReport con trend e alert
        """
        if len(reports) < 2:
            return LongitudinalReport(
                patient_code=reports[0]["patient"]["code"] if reports else "",
                n_sessions=len(reports),
                first_session_date=None,
                last_session_date=None,
                span_days=0,
                summary="Dati insufficienti per analisi longitudinale (serve almeno 2 sessioni).",
            )

        # Ordina per data
        sorted_reports = sorted(reports, key=lambda r: r["session_date"])

        first = sorted_reports[0]
        last = sorted_reports[-1]

        d1 = datetime.fromisoformat(first["session_date"].replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(last["session_date"].replace("Z", "+00:00"))
        span_days = (d2 - d1).days

        # Estrai serie temporali per ogni metrica
        metrics = self._extract_time_series(sorted_reports)

        # Calcola trend per ogni metrica
        trends = {}
        for metric_name, series in metrics.items():
            if len(series["values"]) >= 2:
                trends[metric_name] = self._analyze_trend(metric_name, series)

        # Alert
        alerts = self._generate_alerts(trends)

        # Sintesi
        summary = self._generate_summary(trends, alerts, span_days)

        return LongitudinalReport(
            patient_code=first["patient"]["code"],
            n_sessions=len(sorted_reports),
            first_session_date=first["session_date"],
            last_session_date=last["session_date"],
            span_days=span_days,
            trends=trends,
            alerts=alerts,
            summary=summary,
        )

    def _extract_time_series(self, reports: list[dict]) -> dict[str, dict]:
        """Estrae serie temporali {metric_name: {dates, values}}."""
        series = {}

        for r in reports:
            date = r["session_date"]

            # Score generale (solo se la sessione ha test cognitivi,
            # altrimenti le sessioni di sola analisi lo abbasserebbero a 0)
            if r.get("test_scores"):
                self._append(series, "overall_cognitive_score",
                             date, r.get("overall_cognitive_score", 0))

            # Per ogni test
            for test in r.get("test_scores", []):
                tt = test["test_type"]
                scores = test["scores"]

                if tt == "CPT":
                    self._append(series, f"cpt_attention_score",
                                 date, scores.get("attention_score", 0))
                    self._append(series, f"cpt_rt_variability",
                                 date, scores.get("rt_variability", 0))
                elif tt == "DigitSpan":
                    self._append(series, f"digit_span_fine_grained",
                                 date, scores.get("fine_grained_score", 0))
                    self._append(series, f"digit_span_longest",
                                 date, scores.get("longest_correct", 0))
                elif tt == "Stroop":
                    cw = scores.get("blocks", {}).get("color_word", {})
                    self._append(series, "stroop_cw_accuracy",
                                 date, cw.get("accuracy", 0) * 100)
                    if scores.get("interference_rt_ms") is not None:
                        self._append(series, "stroop_interference_rt",
                                     date, scores["interference_rt_ms"])
                elif tt == "GoNoGo":
                    self._append(series, "gonogo_risk_score",
                                 date, scores.get("screening_risk_score", 0))
                    self._append(series, "gonogo_total_error",
                                 date, scores.get("total_error", 0))

            # Multi-channel
            mc = r.get("multichannel")
            if mc:
                n_audio = mc.get("n_audio_responses", 0)
                # Accetta sia il formato con n_audio > 0 che i valori diretti
                if n_audio > 0 or mc.get("avg_cognitive_strain") is not None:
                    self._append(series, "multichannel_cognitive_strain",
                                 date, mc.get("avg_cognitive_strain", 0))
                    self._append(series, "multichannel_emotional_distress",
                                 date, mc.get("avg_emotional_distress", 0))
                    self._append(series, "multichannel_communication_quality",
                                 date, mc.get("avg_communication_quality", 0))

        return series

    @staticmethod
    def _append(series: dict, name: str, date: str, value: float):
        if name not in series:
            series[name] = {"dates": [], "values": []}
        series[name]["dates"].append(date)
        series[name]["values"].append(value)

    def _analyze_trend(self, name: str, series: dict) -> MetricTrend:
        """Calcola trend, slope, direction, RCI."""
        values = series["values"]
        dates = series["dates"]

        # Slope con regressione lineare semplice (x = indice sessione)
        n = len(values)
        xs = list(range(n))
        slope = self._linear_regression_slope(xs, values)

        # Variazione percentuale prima-ultima
        if values[0] != 0:
            change_pct = ((values[-1] - values[0]) / abs(values[0])) * 100
        else:
            change_pct = 0

        # Direction: dipende se più alto è meglio
        direction = self._determine_direction(name, slope)

        # Reliable Change Index (semplificato: basato su std delle misure)
        if len(values) > 2:
            std = self._std(values)
            if std > 0:
                rci = abs(values[-1] - values[0]) / (std * math.sqrt(2))
            else:
                rci = 0
        else:
            rci = 0

        reliable = rci > self.RCI_CRITICAL

        return MetricTrend(
            metric_name=name,
            values=values,
            dates=dates,
            slope=slope,
            direction=direction,
            change_pct=change_pct,
            reliable_change=reliable,
            rci_value=rci,
        )

    def _determine_direction(self, name: str, slope: float) -> str:
        """Classifica il trend in improving/stable/declining."""
        if abs(slope) < self.SLOPE_STABLE_THRESHOLD:
            return "stable"

        # Metriche in cui aumentare è meglio
        for keyword in self.HIGHER_IS_BETTER:
            if keyword in name:
                return "improving" if slope > 0 else "declining"

        # Metriche in cui diminuire è meglio
        for keyword in self.LOWER_IS_BETTER:
            if keyword in name:
                return "improving" if slope < 0 else "declining"

        return "stable"

    @staticmethod
    def _linear_regression_slope(xs: list, ys: list) -> float:
        """Slope della retta di regressione (metodo dei minimi quadrati)."""
        n = len(xs)
        if n < 2:
            return 0
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
        den = sum((xs[i] - mean_x) ** 2 for i in range(n))
        return num / den if den > 0 else 0

    @staticmethod
    def _std(values: list) -> float:
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(var)

    def _generate_alerts(self, trends: dict) -> list[str]:
        """Genera alert clinici su declini significativi."""
        alerts = []
        for name, trend in trends.items():
            if trend.direction == "declining" and trend.reliable_change:
                alerts.append(
                    f"⚠ {name}: declino significativo ({trend.change_pct:+.1f}%, "
                    f"RCI={trend.rci_value:.2f})"
                )
            elif trend.direction == "declining" and abs(trend.change_pct) > 20:
                alerts.append(
                    f"⚠ {name}: possibile declino ({trend.change_pct:+.1f}%)"
                )
        return alerts

    def _generate_summary(
        self,
        trends: dict,
        alerts: list,
        span_days: int,
    ) -> str:
        """Genera una sintesi testuale dell'andamento."""
        n_improving = sum(1 for t in trends.values() if t.direction == "improving")
        n_declining = sum(1 for t in trends.values() if t.direction == "declining")
        n_stable = sum(1 for t in trends.values() if t.direction == "stable")

        parts = []
        parts.append(f"Periodo di monitoraggio: {span_days} giorni.")
        parts.append(
            f"Analisi di {len(trends)} metriche: {n_improving} in miglioramento, "
            f"{n_stable} stabili, {n_declining} in peggioramento."
        )

        if alerts:
            parts.append(f"Sono presenti {len(alerts)} alert clinici su declini significativi.")
        else:
            parts.append("Nessun declino significativo rilevato (RCI).")

        return " ".join(parts)
