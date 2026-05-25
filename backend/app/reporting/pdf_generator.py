"""
Generatore di report PDF per il medico.

Usa ReportLab per creare PDF professionali che includono:
- Intestazione con dati paziente e sessione
- Tabella dei punteggi per test
- Grafico radar dei tre indicatori multi-canale
- Box di key findings e raccomandazioni
- Footer con firma e disclaimer

Il PDF è generato on-demand dall'endpoint /reports/{session_id}/pdf.
"""

import logging
from datetime import datetime
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether, Image,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False


class PDFReportGenerator:
    """Genera PDF del report clinico."""

    # Colori coerenti col frontend
    PRIMARY = colors.HexColor("#2E5C8A")
    LIGHT_BLUE = colors.HexColor("#D5E8F0")
    ALT_ROW = colors.HexColor("#F0F4F8")
    SUCCESS = colors.HexColor("#43A047")
    WARNING = colors.HexColor("#FB8C00")
    DANGER = colors.HexColor("#E53935")
    TEXT_MUTED = colors.HexColor("#6C757D")

    def __init__(self):
        if not _REPORTLAB_AVAILABLE:
            raise ImportError(
                "reportlab non installato. pip install reportlab"
            )
        self.styles = self._build_styles()

    def _build_styles(self) -> dict:
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "title", parent=base["Title"],
                fontSize=20, textColor=self.PRIMARY,
                spaceAfter=16, alignment=TA_CENTER,
            ),
            "subtitle": ParagraphStyle(
                "subtitle", parent=base["Heading2"],
                fontSize=13, textColor=self.PRIMARY,
                spaceAfter=10, spaceBefore=14,
            ),
            "h3": ParagraphStyle(
                "h3", parent=base["Heading3"],
                fontSize=11, textColor=self.PRIMARY,
                spaceAfter=6, spaceBefore=10,
            ),
            "body": ParagraphStyle(
                "body", parent=base["BodyText"],
                fontSize=10, alignment=TA_JUSTIFY,
                leading=14, spaceAfter=6,
            ),
            "muted": ParagraphStyle(
                "muted", parent=base["BodyText"],
                fontSize=9, textColor=self.TEXT_MUTED,
                alignment=TA_CENTER,
            ),
            "flag": ParagraphStyle(
                "flag", parent=base["BodyText"],
                fontSize=9, leading=12,
            ),
        }

    def generate(self, report: dict) -> bytes:
        """Genera il PDF e lo restituisce come bytes."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
            title=f"Report sessione {report['session_id'][:8]}",
        )

        story = []
        self._add_header(story, report)
        self._add_patient_info(story, report)
        self._add_risk_summary(story, report)
        self._add_test_scores_table(story, report)
        self._add_multichannel_section(story, report)
        self._add_findings_and_recommendations(story, report)
        self._add_footer(story, report)

        doc.build(story, onFirstPage=self._draw_page_number, onLaterPages=self._draw_page_number)
        buffer.seek(0)
        return buffer.read()

    # ============ SEZIONI ============

    def _add_header(self, story, report):
        story.append(Paragraph(
            "Report di Valutazione Cognitiva",
            self.styles["title"]
        ))
        story.append(Paragraph(
            f"Sessione del {self._fmt_date(report['session_date'])} — "
            f"Medico: {report['clinician_id']}",
            self.styles["muted"]
        ))
        story.append(Spacer(1, 0.4 * cm))

    def _add_patient_info(self, story, report):
        patient = report["patient"]
        story.append(Paragraph("Dati paziente", self.styles["subtitle"]))

        data = [
            ["Codice paziente", patient["code"]],
            ["Età", f"{patient['age']} anni"],
            ["Lingua", patient["language"]],
            ["Sospetto clinico", patient.get("clinical_suspicion") or "— nessuno —"],
        ]
        t = Table(data, colWidths=[5 * cm, 12 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), self.LIGHT_BLUE),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    def _add_risk_summary(self, story, report):
        risk = report["overall_risk_level"]
        risk_map = {
            "low": ("Basso", self.SUCCESS, "Profilo cognitivo nella norma."),
            "medium": ("Moderato", self.WARNING, "Alcuni indicatori richiedono attenzione."),
            "high": ("Elevato", self.DANGER, "Necessaria valutazione approfondita."),
        }
        label, color, msg = risk_map.get(risk, ("N/A", colors.grey, ""))

        story.append(Paragraph("Sintesi complessiva", self.styles["subtitle"]))
        data = [
            ["Score cognitivo complessivo", f"{report['overall_cognitive_score']:.1f} / 100"],
            ["Livello di rischio", label],
            ["Interpretazione", msg],
        ]
        t = Table(data, colWidths=[6 * cm, 11 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), self.LIGHT_BLUE),
            ("BACKGROUND", (1, 1), (1, 1), color),
            ("TEXTCOLOR", (1, 1), (1, 1), colors.white),
            ("FONTNAME", (1, 1), (1, 1), "Helvetica-Bold"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    def _add_test_scores_table(self, story, report):
        story.append(Paragraph("Risultati per test", self.styles["subtitle"]))

        test_scores = report.get("test_scores", [])
        if not test_scores:
            story.append(Paragraph("Nessun test somministrato.", self.styles["body"]))
            return

        data = [["Test", "Metrica principale", "Valore", "Flag"]]
        for t in test_scores:
            metric_name, value = self._extract_main_metric(t)
            flags = ", ".join(t.get("flags", [])) or "—"
            data.append([t["test_type"], metric_name, value, flags])

        tbl = Table(data, colWidths=[3 * cm, 5 * cm, 3 * cm, 6 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, self.ALT_ROW]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tbl)

        # Note cliniche per test
        for t in test_scores:
            if t.get("clinical_note"):
                story.append(Paragraph(
                    f"<b>{t['test_type']}:</b> {t['clinical_note']}",
                    self.styles["flag"]
                ))
        story.append(Spacer(1, 0.3 * cm))

    def _add_multichannel_section(self, story, report):
        mc = report.get("multichannel")
        if not mc:
            return

        story.append(Paragraph("Analisi multi-canale", self.styles["subtitle"]))
        n = mc.get("n_audio_responses", 0)
        story.append(Paragraph(
            (f"Integrazione di {n} risposta/e con pipeline NLP + Prosodia + Sentiment/Emotion."
             if n else
             "Analisi linguistica, sentiment ed emozioni della risposta verbale."),
            self.styles["body"]
        ))

        data = [
            ["Indicatore", "Valore (0-100)", "Interpretazione"],
            ["Cognitive Strain", f"{mc['avg_cognitive_strain']:.1f}",
             self._interpret_strain(mc['avg_cognitive_strain'])],
            ["Emotional Distress", f"{mc['avg_emotional_distress']:.1f}",
             self._interpret_distress(mc['avg_emotional_distress'])],
            ["Communication Quality", f"{mc['avg_communication_quality']:.1f}",
             self._interpret_quality(mc['avg_communication_quality'])],
        ]
        t = Table(data, colWidths=[4.5 * cm, 3 * cm, 9.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

        # Dettaglio completo per ogni analisi (come nella pagina web)
        details = report.get("analyses_detail") or []
        if details:
            story.append(Paragraph("Dettaglio analisi", self.styles["subtitle"]))
        for a in details:
            self._add_analysis_detail(story, a)

    def _simple_table(self, story, data, col_widths):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25 * cm))

    def _add_analysis_detail(self, story, a):
        """Riproduce nel PDF tutte le sezioni mostrate a schermo per una analisi."""
        # --- Trascrizione ---
        transcript = a.get("transcript") or a.get("text")
        if transcript:
            story.append(Paragraph("Trascrizione analizzata", self.styles["h3"]))
            story.append(Paragraph(str(transcript), self.styles["body"]))
            story.append(Spacer(1, 0.2 * cm))

        # --- Indicatori compositi ---
        strain = float(a.get("cognitive_strain_index", 0) or 0)
        distress = float(a.get("emotional_distress_index", 0) or 0)
        quality = float(a.get("communication_quality_index", 0) or 0)
        self._simple_table(story, [
            ["Indicatore", "Valore (0-100)", "Interpretazione"],
            ["Sforzo cognitivo", f"{strain:.1f}", self._interpret_strain(strain)],
            ["Disagio emotivo", f"{distress:.1f}", self._interpret_distress(distress)],
            ["Qualita comunicazione", f"{quality:.1f}", self._interpret_quality(quality)],
        ], [4.5 * cm, 3 * cm, 9.5 * cm])

        # --- Profilo linguistico ---
        ling = a.get("linguistic") or {}
        if ling:
            story.append(Paragraph("Profilo linguistico", self.styles["h3"]))
            labels = [
                ("word_count", "Numero parole"),
                ("sentence_count", "Numero frasi"),
                ("mean_sentence_length", "Lunghezza media frase"),
                ("lexical_diversity", "Diversita lessicale (TTR)"),
                ("mattr", "MATTR"),
                ("lexical_density", "Densita lessicale"),
                ("cohesion", "Coesione"),
                ("mean_syntactic_depth", "Profondita sintattica media"),
            ]
            rows = [["Metrica", "Valore"]]
            for key, lab in labels:
                if ling.get(key) is not None:
                    v = ling[key]
                    rows.append([lab, f"{v:.3f}" if isinstance(v, float) else str(v)])
            if len(rows) > 1:
                self._simple_table(story, rows, [9 * cm, 8 * cm])

            pos = ling.get("pos_distribution") or {}
            if pos:
                story.append(Paragraph("Distribuzione grammaticale (POS)", self.styles["body"]))
                pos_rows = [["Categoria", "Frequenza"]]
                for k, v in sorted(pos.items(), key=lambda x: -float(x[1]))[:12]:
                    pos_rows.append([str(k), f"{float(v) * 100:.1f}%"])
                self._simple_table(story, pos_rows, [9 * cm, 8 * cm])

        # --- Profilo prosodico (se audio) ---
        pros = a.get("prosodic") or {}
        if pros:
            story.append(Paragraph("Profilo vocale (prosodia)", self.styles["h3"]))
            rows = [["Metrica", "Valore"]]
            for k, v in pros.items():
                if isinstance(v, (int, float)):
                    rows.append([str(k), f"{v:.2f}" if isinstance(v, float) else str(v)])
            if len(rows) > 1:
                self._simple_table(story, rows, [9 * cm, 8 * cm])

        # --- Stato emotivo ---
        sent = a.get("sentiment") or {}
        emo = a.get("emotion") or {}
        if sent or emo:
            story.append(Paragraph("Stato emotivo", self.styles["h3"]))
            if sent.get("label"):
                story.append(Paragraph(
                    f"Sentiment: {sent.get('label')} (confidenza {float(sent.get('score', 0)):.2f})",
                    self.styles["body"],
                ))
            emotions = emo.get("emotions") or {}
            if emotions:
                erows = [["Emozione", "Probabilita"]]
                for k, v in sorted(emotions.items(), key=lambda x: -float(x[1])):
                    erows.append([str(k), f"{float(v) * 100:.1f}%"])
                self._simple_table(story, erows, [9 * cm, 8 * cm])
            elif emo.get("dominant"):
                story.append(Paragraph(
                    f"Emozione dominante: {emo.get('dominant')} "
                    f"({float(emo.get('dominant_score', 0)):.2f})",
                    self.styles["body"],
                ))

        story.append(Spacer(1, 0.4 * cm))

    def _add_findings_and_recommendations(self, story, report):
        findings = report.get("key_findings", [])
        recs = report.get("recommendations", [])

        if findings:
            story.append(Paragraph("Osservazioni chiave", self.styles["subtitle"]))
            for f in findings:
                story.append(Paragraph(f"• {f}", self.styles["body"]))

        if recs:
            story.append(Paragraph("Raccomandazioni", self.styles["subtitle"]))
            for r in recs:
                story.append(Paragraph(f"• {r}", self.styles["body"]))

    def _add_footer(self, story, report):
        story.append(Spacer(1, 0.8 * cm))
        story.append(Paragraph(
            "<i>Report generato automaticamente dalla piattaforma di valutazione cognitiva. "
            "I risultati non sostituiscono la valutazione clinica di un professionista qualificato.</i>",
            self.styles["muted"]
        ))
        story.append(Paragraph(
            f"ID sessione: {report['session_id']} · "
            f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            self.styles["muted"]
        ))

    def _draw_page_number(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(self.TEXT_MUTED)
        canvas.drawRightString(
            A4[0] - 2 * cm, 1.5 * cm,
            f"Pagina {doc.page}"
        )
        canvas.restoreState()

    # ============ HELPERS ============

    @staticmethod
    def _fmt_date(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return iso or ""

    @staticmethod
    def _extract_main_metric(test: dict) -> tuple[str, str]:
        tt = test["test_type"]
        s = test["scores"]
        if tt == "CPT":
            return "Attention Score", f"{s.get('attention_score', 0):.1f}"
        if tt == "DigitSpan":
            return "Fine-grained Score", f"{s.get('fine_grained_score', 0):.1f}"
        if tt == "Stroop":
            cw = s.get("blocks", {}).get("color_word", {})
            acc = cw.get("accuracy", 0) * 100 if cw else 0
            return "CW Accuracy", f"{acc:.1f}%"
        if tt == "GoNoGo":
            return "Risk Score", f"{s.get('screening_risk_score', 0):.1f}"
        return "—", "—"

    @staticmethod
    def _interpret_strain(v: float) -> str:
        if v < 25: return "Basso — performance fluida"
        if v < 50: return "Moderato — sforzo nella norma"
        if v < 75: return "Alto — difficoltà evidenti"
        return "Molto alto — compromissione significativa"

    @staticmethod
    def _interpret_distress(v: float) -> str:
        if v < 25: return "Basso — stato emotivo sereno"
        if v < 50: return "Moderato — lieve tensione"
        if v < 75: return "Alto — distress emotivo rilevante"
        return "Molto alto — valutare supporto psicologico"

    @staticmethod
    def _interpret_quality(v: float) -> str:
        if v > 75: return "Ottima comunicazione"
        if v > 50: return "Comunicazione nella norma"
        if v > 25: return "Compromissione moderata"
        return "Comunicazione significativamente compromessa"
