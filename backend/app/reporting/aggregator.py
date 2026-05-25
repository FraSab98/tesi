"""
Aggregatore di dati per la generazione dei report.

Prende in input una session_id e produce un SessionReport completo
che include:
- Dati anagrafici del paziente
- Punteggi cognitivi per ogni test (dalla Fase 2)
- Analisi multi-canale per risposte audio/narrative (dalla Fase 6)
- Indicatori compositi aggregati a livello di sessione
- Flag clinici (alert su valori fuori norma)
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Descrizioni leggibili dei flag clinici: il medico legge la spiegazione,
# non il codice interno. Il codice resta disponibile per logica/frontend.
FLAG_DESCRIPTIONS = {
    "attention_score_low":        "Attenzione sostenuta sotto la soglia clinica.",
    "high_rt_variability":        "Tempi di reazione molto irregolari: l'attenzione oscilla nel tempo (pattern compatibile con ADHD/MCI).",
    "high_omission_rate":         "Molti bersagli mancati: difficolta a mantenere l'attenzione nel tempo.",
    "high_attention_instability": "Instabilita attentiva combinata elevata (variabilita dei tempi di reazione + lapsus).",
    "low_fine_grained":           "Accuratezza fine della ripetizione bassa (distanza di edit elevata): segnale precoce di MCI (Asgari 2020).",
    "low_span":                   "Span di memoria sotto la norma per l'eta adulta.",
    "high_interference":          "Forte effetto interferenza Stroop: difficolta di inibizione/controllo cognitivo.",
    "low_cw_accuracy":            "Accuratezza bassa nella condizione incongruente (parola-colore).",
    "above_mmse_cutoff":          "Numero di errori oltre il cut-off MMSE: compromissione marcata.",
    "above_moca_cutoff":          "Numero di errori oltre il cut-off MoCA: possibile decadimento cognitivo lieve.",
    "high_risk_score":            "Punteggio di rischio dello screening elevato.",
}


@dataclass
class TestScoreSummary:
    """Riepilogo del punteggio di un singolo test in una sessione."""
    test_type: str
    test_config_id: str
    scores: dict
    flags: list = field(default_factory=list)  # alert clinici
    clinical_note: str = ""


@dataclass
class MultiChannelSummary:
    """Sintesi degli indicatori compositi della Fase 6 per la sessione."""
    avg_cognitive_strain: float = 0.0
    avg_emotional_distress: float = 0.0
    avg_communication_quality: float = 0.0
    n_audio_responses: int = 0
    dominant_emotions: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionReport:
    """Report completo di una sessione, pronto per la visualizzazione."""
    # Metadata
    session_id: str
    session_date: datetime
    clinician_id: str
    patient_code: str
    patient_age: int
    patient_language: str
    patient_clinical_suspicion: Optional[str]

    # Score per test (output Fase 2 scoring)
    test_scores: list[TestScoreSummary] = field(default_factory=list)

    # Analisi multi-canale (Fase 6)
    multichannel: Optional[MultiChannelSummary] = None

    # Metriche aggregate a livello sessione
    overall_cognitive_score: float = 0.0  # media pesata dei test
    overall_risk_level: str = "low"        # low | medium | high
    key_findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "session_date": self.session_date.isoformat() if self.session_date else None,
            "clinician_id": self.clinician_id,
            "patient": {
                "code": self.patient_code,
                "age": self.patient_age,
                "language": self.patient_language,
                "clinical_suspicion": self.patient_clinical_suspicion,
            },
            "test_scores": [
                {
                    "test_type": t.test_type,
                    "scores": t.scores,
                    "flags": [
                        {
                            "code": f,
                            "description": FLAG_DESCRIPTIONS.get(f, f),
                            "severity": ReportAggregator.FLAG_SEVERITY.get(f, 1),
                        }
                        for f in t.flags
                    ],
                    "clinical_note": t.clinical_note,
                }
                for t in self.test_scores
            ],
            "multichannel": self.multichannel.to_dict() if self.multichannel else None,
            "overall_cognitive_score": round(self.overall_cognitive_score, 1),
            "overall_risk_level": self.overall_risk_level,
            "key_findings": self.key_findings,
            "recommendations": self.recommendations,
        }


class ReportAggregator:
    """
    Aggrega i dati di una sessione in un report clinico strutturato.
    Applica regole cliniche (flag, raccomandazioni) basate sulla letteratura.
    """

    # Soglie derivate dai paper dello stato dell'arte
    THRESHOLDS = {
        "CPT": {
            "attention_score_low": 60,       # < 60 = problematico
            "rt_variability_high": 0.30,     # > 0.30 = alta variabilità (Paper 4)
            "omission_rate_high": 0.15,
        },
        "DigitSpan": {
            "fine_grained_low": 70,          # Paper 5: cut-off discriminativo
            "conventional_low": 50,
        },
        "Stroop": {
            "interference_rt_high": 500,     # ms di penalità interferenza
            "accuracy_cw_low": 0.85,
        },
        "GoNoGo": {
            "risk_score_high": 70,           # Paper 9: cut-off screening
            "total_error_high": 6,           # cut-off MMSE
            "total_error_mild": 2,           # cut-off MoCA
        },
    }

    # Gravita dei flag clinici: usata per pesare il livello di rischio.
    # 3 = severo, 2 = moderato, 1 = lieve/aspecifico. Da calibrare sui dati.
    FLAG_SEVERITY = {
        "attention_score_low":        3,
        "above_mmse_cutoff":          3,
        "high_risk_score":            3,
        "low_span":                   3,
        "high_omission_rate":         2,
        "low_fine_grained":           2,
        "high_interference":          2,
        "above_moca_cutoff":          2,
        "high_attention_instability": 2,
        "high_rt_variability":        1,
        "low_cw_accuracy":            1,
    }
    DEFAULT_FLAG_WEIGHT = 1

    def build_report(
        self,
        session: dict,
        patient: dict,
        test_scores: list[dict],
        analysis_results: list[dict] = None,
    ) -> SessionReport:
        """
        Costruisce il report completo.

        Args:
            session: dict con session_id, created_at, clinician_id
            patient: dict con code, age, language, clinical_suspicion
            test_scores: lista di score dalla tabella cognitive_scores
            analysis_results: lista di risultati multi-canale dalla Fase 6
        """
        # Processa test scores
        test_summaries = [
            self._summarize_test(ts) for ts in test_scores
        ]

        # Aggrega multi-canale
        mc_summary = self._summarize_multichannel(analysis_results or [])

        # Score cognitivo complessivo
        overall_score = self._compute_overall_score(test_summaries)

        # Risk level
        risk_level = self._determine_risk_level(test_summaries, mc_summary, overall_score)

        # Key findings e raccomandazioni
        findings = self._extract_key_findings(test_summaries, mc_summary)
        recommendations = self._generate_recommendations(
            test_summaries, mc_summary, risk_level, patient
        )

        return SessionReport(
            session_id=session["id"],
            session_date=session.get("created_at") or datetime.now(),
            clinician_id=session["clinician_id"],
            patient_code=patient["external_code"],
            patient_age=patient["age"],
            patient_language=patient["language"],
            patient_clinical_suspicion=patient.get("clinical_suspicion"),
            test_scores=test_summaries,
            multichannel=mc_summary,
            overall_cognitive_score=overall_score,
            overall_risk_level=risk_level,
            key_findings=findings,
            recommendations=recommendations,
        )

    # ============ SUMMARY PER TEST ============

    def _summarize_test(self, ts: dict) -> TestScoreSummary:
        """Crea summary con flag clinici per un singolo test."""
        test_type = ts["test_type"]
        scores = ts["scores"]
        flags = []
        note = ""

        if test_type == "CPT":
            flags, note = self._flag_cpt(scores)
        elif test_type == "DigitSpan":
            flags, note = self._flag_digit_span(scores)
        elif test_type == "Stroop":
            flags, note = self._flag_stroop(scores)
        elif test_type == "GoNoGo":
            flags, note = self._flag_go_nogo(scores)

        return TestScoreSummary(
            test_type=test_type,
            test_config_id=ts.get("test_config_id", ""),
            scores=scores,
            flags=flags,
            clinical_note=note,
        )

    def _flag_cpt(self, s: dict) -> tuple[list[str], str]:
        flags = []
        th = self.THRESHOLDS["CPT"]
        notes = []

        if s.get("attention_score", 100) < th["attention_score_low"]:
            flags.append("attention_score_low")
            notes.append("Score attenzione sotto soglia clinica")

        if s.get("rt_variability", 0) > th["rt_variability_high"]:
            flags.append("high_rt_variability")
            notes.append("Alta variabilità nei tempi di reazione (coerente con ADHD/MCI)")

        if s.get("omission_rate", 0) > th["omission_rate_high"]:
            flags.append("high_omission_rate")
            notes.append("Molte omissioni (problemi di attenzione sostenuta)")

        return flags, "; ".join(notes)

    def _flag_digit_span(self, s: dict) -> tuple[list[str], str]:
        flags = []
        th = self.THRESHOLDS["DigitSpan"]
        notes = []

        if s.get("fine_grained_score", 100) < th["fine_grained_low"]:
            flags.append("low_fine_grained")
            notes.append("Punteggio Levenshtein sotto cut-off (Paper 5: correla con MCI)")

        longest = s.get("longest_correct", 0)
        if longest < 4:
            flags.append("low_span")
            notes.append(f"Span massimo raggiunto: {longest} (sotto la norma per adulti)")

        return flags, "; ".join(notes)

    def _flag_stroop(self, s: dict) -> tuple[list[str], str]:
        flags = []
        th = self.THRESHOLDS["Stroop"]
        notes = []

        if s.get("interference_rt_ms") and s["interference_rt_ms"] > th["interference_rt_high"]:
            flags.append("high_interference")
            notes.append("Alta interferenza Stroop (difficoltà di inibizione)")

        cw_block = s.get("blocks", {}).get("color_word", {})
        if cw_block and cw_block.get("accuracy", 1) < th["accuracy_cw_low"]:
            flags.append("low_cw_accuracy")
            notes.append("Accuratezza bassa in condizione incongruente")

        return flags, "; ".join(notes)

    def _flag_go_nogo(self, s: dict) -> tuple[list[str], str]:
        flags = []
        th = self.THRESHOLDS["GoNoGo"]
        notes = []

        total_err = s.get("total_error", 0)
        risk = s.get("screening_risk_score", 0)

        if total_err > th["total_error_high"]:
            flags.append("above_mmse_cutoff")
            notes.append(f"{total_err} errori: oltre cut-off MMSE (Paper 9)")
        elif total_err > th["total_error_mild"]:
            flags.append("above_moca_cutoff")
            notes.append(f"{total_err} errori: oltre cut-off MoCA (possibile MCI)")

        if risk > th["risk_score_high"]:
            flags.append("high_risk_score")
            notes.append(f"Risk score {risk:.0f}/100 elevato")

        return flags, "; ".join(notes)

    # ============ MULTI-CHANNEL SUMMARY ============

    def _summarize_multichannel(self, analyses: list[dict]) -> MultiChannelSummary:
        """Aggrega le analisi multi-canale a livello sessione."""
        if not analyses:
            return MultiChannelSummary()

        strains = [a.get("cognitive_strain_index", 0) for a in analyses]
        distresses = [a.get("emotional_distress_index", 0) for a in analyses]
        qualities = [a.get("communication_quality_index", 0) for a in analyses]

        # Emozioni dominanti aggregate
        dominant_counts = {}
        for a in analyses:
            emo = a.get("emotion", {})
            if emo:
                dom = emo.get("dominant")
                if dom:
                    dominant_counts[dom] = dominant_counts.get(dom, 0) + 1

        return MultiChannelSummary(
            avg_cognitive_strain=sum(strains) / len(strains) if strains else 0,
            avg_emotional_distress=sum(distresses) / len(distresses) if distresses else 0,
            avg_communication_quality=sum(qualities) / len(qualities) if qualities else 0,
            n_audio_responses=len(analyses),
            dominant_emotions=dominant_counts,
        )

    # ============ AGGREGAZIONE COMPLESSIVA ============

    def _compute_overall_score(self, summaries: list[TestScoreSummary]) -> float:
        """Score cognitivo 0-100 complessivo (media pesata)."""
        if not summaries:
            return 0.0

        scores = []
        for s in summaries:
            if s.test_type == "CPT":
                scores.append(s.scores.get("attention_score", 0))
            elif s.test_type == "DigitSpan":
                scores.append(s.scores.get("fine_grained_score", 0))
            elif s.test_type == "Stroop":
                cw = s.scores.get("blocks", {}).get("color_word", {})
                scores.append(cw.get("accuracy", 0) * 100 if cw else 0)
            elif s.test_type == "GoNoGo":
                # Inverso del risk score
                scores.append(100 - s.scores.get("screening_risk_score", 0))

        return sum(scores) / len(scores) if scores else 0.0

    def _determine_risk_level(
        self,
        summaries: list[TestScoreSummary],
        mc: MultiChannelSummary,
        overall: float,
    ) -> str:
        """Livello di rischio basato sulla gravita *pesata* dei flag, non sul conteggio.

        Un flag severo pesa piu di tre flag lievi, cosi un profilo uniformemente
        lieve non viene escalato a 'high' solo per accumulo di segnali deboli.
        """
        weighted = 0
        has_severe = False
        for s in summaries:
            for f in s.flags:
                w = self.FLAG_SEVERITY.get(f, self.DEFAULT_FLAG_WEIGHT)
                weighted += w
                if w >= 3:
                    has_severe = True

        # Il multicanale incide, ma con peso cognitivo contenuto
        if mc.avg_cognitive_strain > 50:
            weighted += 2
        if mc.avg_emotional_distress > 60:
            weighted += 1  # contributo emotivo, non cognitivo

        # Se non ci sono test cognitivi (es. sessione di sola analisi multi-canale),
        # il punteggio cognitivo e 0 solo perche assente: non deve forzare 'high'.
        has_cognitive = len(summaries) > 0

        # Decisione: serve gravita reale per arrivare a 'high'
        if (has_cognitive and overall < 50) or weighted >= 9 or (has_severe and weighted >= 6):
            return "high"
        if (has_cognitive and overall < 70) or weighted >= 4 or has_severe or mc.avg_cognitive_strain > 50:
            return "medium"
        return "low"

    def _extract_key_findings(
        self,
        summaries: list[TestScoreSummary],
        mc: MultiChannelSummary,
    ) -> list[str]:
        """Estrae le osservazioni chiave per il medico."""
        findings = []

        for s in summaries:
            if s.clinical_note:
                findings.append(f"{s.test_type}: {s.clinical_note}")

        if mc.n_audio_responses > 0:
            if mc.avg_cognitive_strain > 50:
                findings.append(
                    f"Analisi multi-canale: strain cognitivo elevato "
                    f"({mc.avg_cognitive_strain:.0f}/100) coerente con affaticamento"
                )
            if mc.avg_emotional_distress > 50:
                findings.append(
                    f"Analisi multi-canale: distress emotivo elevato "
                    f"({mc.avg_emotional_distress:.0f}/100)"
                )
            if mc.avg_communication_quality < 40:
                findings.append(
                    f"Analisi multi-canale: qualità comunicativa compromessa "
                    f"({mc.avg_communication_quality:.0f}/100)"
                )

        return findings

    def _generate_recommendations(
        self,
        summaries: list[TestScoreSummary],
        mc: MultiChannelSummary,
        risk: str,
        patient: dict,
    ) -> list[str]:
        """Genera raccomandazioni cliniche basate sui risultati."""
        recs = []

        if risk == "high":
            recs.append(
                "Si raccomanda valutazione neuropsicologica approfondita con batteria clinica completa."
            )
            recs.append(
                "Considerare imaging cerebrale (MRI) e valutazione neurologica specialistica."
            )
        elif risk == "medium":
            recs.append(
                "Si suggerisce follow-up a 6 mesi per monitorare eventuali cambiamenti."
            )
            recs.append(
                "Approfondire con MoCA o batteria neuropsicologica selettiva."
            )
        else:
            recs.append(
                "Profilo cognitivo nella norma. Follow-up annuale di routine."
            )

        # Raccomandazioni specifiche per test
        has_adhd_pattern = any("high_rt_variability" in s.flags for s in summaries)
        if has_adhd_pattern and patient.get("age", 0) < 30:
            recs.append(
                "Pattern compatibile con ADHD: considerare valutazione specialistica."
            )

        if mc.avg_emotional_distress > 60:
            recs.append(
                "Distress emotivo rilevante: considerare supporto psicologico."
            )

        return recs
