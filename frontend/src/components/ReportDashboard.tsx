/**
 * ReportDashboard — pagina di reporting per il medico.
 *
 * Mostra:
 * - Metadata sessione e paziente
 * - Livello di rischio con badge colorato
 * - Radar chart dei 3 indicatori multi-canale
 * - Bar chart dei punteggi per test
 * - Lista flag clinici e raccomandazioni
 * - Pulsante export PDF
 */

import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ResponsiveContainer,
} from "recharts";

// ============ TYPES ============

interface TestScore {
  test_type: string;
  scores: Record<string, unknown>;
  flags: string[];
  clinical_note: string;
}

interface MultichannelSummary {
  avg_cognitive_strain: number;
  avg_emotional_distress: number;
  avg_communication_quality: number;
  n_audio_responses: number;
  dominant_emotions: Record<string, number>;
}

export interface SessionReportData {
  session_id: string;
  session_date: string;
  clinician_id: string;
  patient: {
    code: string;
    age: number;
    language: string;
    clinical_suspicion?: string;
  };
  test_scores: TestScore[];
  multichannel?: MultichannelSummary;
  overall_cognitive_score: number;
  overall_risk_level: "low" | "medium" | "high";
  key_findings: string[];
  recommendations: string[];
}

interface Props {
  report: SessionReportData;
  onExportPdf?: () => void;
}

// ============ HELPERS ============

const RISK_COLORS: Record<string, string> = {
  low: "#43A047",
  medium: "#FB8C00",
  high: "#E53935",
};

const RISK_LABELS: Record<string, string> = {
  low: "Rischio basso",
  medium: "Rischio moderato",
  high: "Rischio elevato",
};

function extractMainMetric(t: TestScore): { label: string; value: number } {
  const s = t.scores as Record<string, unknown>;
  switch (t.test_type) {
    case "CPT":
      return { label: "Attention Score", value: Number(s.attention_score) || 0 };
    case "DigitSpan":
      return { label: "Fine-grained Score", value: Number(s.fine_grained_score) || 0 };
    case "Stroop": {
      const blocks = s.blocks as Record<string, { accuracy: number }> | undefined;
      const acc = blocks?.color_word?.accuracy ?? 0;
      return { label: "CW Accuracy", value: acc * 100 };
    }
    case "GoNoGo":
      return { label: "Quality (100-risk)", value: 100 - (Number(s.screening_risk_score) || 0) };
    default:
      return { label: "—", value: 0 };
  }
}

// ============ COMPONENT ============

export function ReportDashboard({ report, onExportPdf }: Props) {
  const [downloading, setDownloading] = useState(false);

  const testBarData = report.test_scores.map(t => {
    const m = extractMainMetric(t);
    return {
      name: t.test_type,
      score: Math.round(m.value * 10) / 10,
      metric: m.label,
    };
  });

  const mc = report.multichannel;
  const radarData = mc && mc.n_audio_responses > 0
    ? [
        { dimension: "Strain\n(inverso)", value: 100 - mc.avg_cognitive_strain, fullMark: 100 },
        { dimension: "Serenità\nemotiva", value: 100 - mc.avg_emotional_distress, fullMark: 100 },
        { dimension: "Qualità\ncomunicazione", value: mc.avg_communication_quality, fullMark: 100 },
      ]
    : null;

  const riskColor = RISK_COLORS[report.overall_risk_level];
  const riskLabel = RISK_LABELS[report.overall_risk_level];

  const handleExport = async () => {
    if (!onExportPdf) return;
    setDownloading(true);
    try {
      await onExportPdf();
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Report di Valutazione Cognitiva</h1>
          <p style={styles.subtitle}>
            Sessione del {new Date(report.session_date).toLocaleString("it-IT")}
            {" · "}Medico: {report.clinician_id}
          </p>
        </div>
        {onExportPdf && (
          <button
            style={{ ...styles.exportButton, opacity: downloading ? 0.6 : 1 }}
            onClick={handleExport}
            disabled={downloading}
          >
            {downloading ? "Generazione..." : "📄 Scarica PDF"}
          </button>
        )}
      </div>

      {/* Patient + Risk */}
      <div style={styles.topGrid}>
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>Paziente</h3>
          <InfoRow label="Codice" value={report.patient.code} />
          <InfoRow label="Età" value={`${report.patient.age} anni`} />
          <InfoRow label="Lingua" value={report.patient.language} />
          <InfoRow
            label="Sospetto clinico"
            value={report.patient.clinical_suspicion || "— nessuno —"}
          />
        </div>

        <div style={{ ...styles.card, ...styles.riskCard, borderColor: riskColor }}>
          <h3 style={styles.cardTitle}>Sintesi</h3>
          <div style={styles.scoreBig}>
            {report.overall_cognitive_score.toFixed(1)}
            <span style={styles.scoreMax}>/100</span>
          </div>
          <div style={{ ...styles.riskBadge, background: riskColor }}>
            {riskLabel}
          </div>
        </div>
      </div>

      {/* Charts */}
      <div style={styles.chartsGrid}>
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>Punteggi per test</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={testBarData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 100]} />
              <Tooltip
                formatter={(value: number, _: string, props: { payload: { metric: string } }) =>
                  [`${value}`, props.payload.metric]
                }
              />
              <Bar dataKey="score" fill="#2E5C8A" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {radarData && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>
              Analisi multi-canale
              <span style={styles.note}>
                {" "}({mc!.n_audio_responses} risposte audio)
              </span>
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="dimension" />
                <PolarRadiusAxis domain={[0, 100]} />
                <Radar
                  name="Paziente"
                  dataKey="value"
                  stroke="#2E5C8A"
                  fill="#2E5C8A"
                  fillOpacity={0.5}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Flags per test */}
      <div style={styles.card}>
        <h3 style={styles.cardTitle}>Dettaglio test</h3>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Test</th>
              <th style={styles.th}>Metrica</th>
              <th style={styles.th}>Valore</th>
              <th style={styles.th}>Flag</th>
            </tr>
          </thead>
          <tbody>
            {report.test_scores.map((t, i) => {
              const m = extractMainMetric(t);
              return (
                <tr key={i} style={{
                  background: i % 2 === 0 ? "white" : "#F0F4F8",
                }}>
                  <td style={styles.td}><strong>{t.test_type}</strong></td>
                  <td style={styles.td}>{m.label}</td>
                  <td style={styles.td}>{m.value.toFixed(1)}</td>
                  <td style={styles.td}>
                    {t.flags.length === 0 ? (
                      <span style={{ color: "#43A047" }}>✓ nella norma</span>
                    ) : (
                      t.flags.map(f => (
                        <span key={f} style={styles.flagBadge}>{f}</span>
                      ))
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Findings e raccomandazioni */}
      <div style={styles.bottomGrid}>
        {report.key_findings.length > 0 && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>Osservazioni chiave</h3>
            <ul style={styles.list}>
              {report.key_findings.map((f, i) => (
                <li key={i} style={styles.listItem}>{f}</li>
              ))}
            </ul>
          </div>
        )}

        {report.recommendations.length > 0 && (
          <div style={styles.card}>
            <h3 style={styles.cardTitle}>Raccomandazioni</h3>
            <ul style={styles.list}>
              {report.recommendations.map((r, i) => (
                <li key={i} style={styles.listItem}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.infoRow}>
      <span style={styles.infoLabel}>{label}</span>
      <span style={styles.infoValue}>{value}</span>
    </div>
  );
}

// ============ STYLES ============

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: "1200px", margin: "0 auto", padding: "2rem",
    fontFamily: "system-ui, sans-serif",
  },
  header: {
    display: "flex", justifyContent: "space-between", alignItems: "flex-start",
    marginBottom: "2rem", gap: "1rem", flexWrap: "wrap",
  },
  title: { margin: 0, color: "#2E5C8A", fontSize: "1.8rem" },
  subtitle: { color: "#6C757D", margin: "0.3rem 0 0 0" },
  exportButton: {
    padding: "0.75rem 1.5rem", fontSize: "1rem", background: "#2E5C8A",
    color: "white", border: "none", borderRadius: "8px", cursor: "pointer",
    whiteSpace: "nowrap",
  },
  topGrid: {
    display: "grid", gridTemplateColumns: "2fr 1fr",
    gap: "1.5rem", marginBottom: "1.5rem",
  },
  chartsGrid: {
    display: "grid", gridTemplateColumns: "1fr 1fr",
    gap: "1.5rem", marginBottom: "1.5rem",
  },
  bottomGrid: {
    display: "grid", gridTemplateColumns: "1fr 1fr",
    gap: "1.5rem", marginTop: "1.5rem",
  },
  card: {
    background: "#f8f9fa", padding: "1.5rem", borderRadius: "12px",
    border: "1px solid #dee2e6",
  },
  riskCard: {
    borderWidth: "3px", borderStyle: "solid",
    display: "flex", flexDirection: "column", alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: {
    margin: "0 0 1rem 0", color: "#2E5C8A", fontSize: "1.05rem",
  },
  scoreBig: {
    fontSize: "3.5rem", fontWeight: "bold", color: "#2E5C8A",
    lineHeight: 1, margin: "0.5rem 0",
  },
  scoreMax: {
    fontSize: "1.5rem", color: "#6C757D", fontWeight: "normal",
  },
  riskBadge: {
    color: "white", padding: "0.5rem 1.5rem", borderRadius: "20px",
    fontWeight: "bold", marginTop: "1rem",
  },
  infoRow: {
    display: "flex", justifyContent: "space-between",
    padding: "0.4rem 0", borderBottom: "1px solid #eee",
  },
  infoLabel: { color: "#6C757D", fontSize: "0.9rem" },
  infoValue: { fontWeight: 500 },
  note: { fontSize: "0.85rem", color: "#6C757D", fontWeight: "normal" },
  table: {
    width: "100%", borderCollapse: "collapse", fontSize: "0.9rem",
  },
  th: {
    textAlign: "left", padding: "0.75rem", background: "#2E5C8A",
    color: "white",
  },
  td: { padding: "0.75rem" },
  flagBadge: {
    display: "inline-block", padding: "0.2rem 0.6rem",
    background: "#FB8C00", color: "white", borderRadius: "4px",
    fontSize: "0.75rem", margin: "0.1rem",
  },
  list: { margin: 0, paddingLeft: "1.2rem" },
  listItem: { marginBottom: "0.5rem", lineHeight: 1.5 },
};
