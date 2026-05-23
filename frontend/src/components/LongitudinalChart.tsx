/**
 * LongitudinalChart — visualizza il trend multi-sessione di un paziente.
 *
 * Mostra:
 * - Line chart per ogni metrica tracciata
 * - Alert clinici prominenti
 * - Sintesi testuale dell'andamento
 */

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";

interface MetricTrend {
  metric_name: string;
  values: number[];
  dates: string[];
  slope: number;
  direction: "improving" | "stable" | "declining";
  change_pct: number;
  reliable_change: boolean;
  rci_value: number;
}

interface LongitudinalReportData {
  patient_code: string;
  n_sessions: number;
  first_session_date: string;
  last_session_date: string;
  span_days: number;
  trends: Record<string, MetricTrend>;
  alerts: string[];
  summary: string;
}

interface Props {
  report: LongitudinalReportData;
}

const DIRECTION_ICON = {
  improving: "↗",
  stable: "→",
  declining: "↘",
};

const DIRECTION_COLOR = {
  improving: "#43A047",
  stable: "#6C757D",
  declining: "#E53935",
};

// Metriche chiave da mostrare nel grafico principale
const KEY_METRICS = [
  "overall_cognitive_score",
  "cpt_attention_score",
  "digit_span_fine_grained",
  "stroop_cw_accuracy",
];

export function LongitudinalChart({ report }: Props) {
  // Prepara dati per LineChart: un array dove ogni punto ha tutte le metriche
  const firstTrend = Object.values(report.trends)[0];
  if (!firstTrend) {
    return (
      <div style={styles.container}>
        <p>Nessun dato di trend disponibile.</p>
      </div>
    );
  }

  const chartData = firstTrend.dates.map((date, i) => {
    const row: Record<string, unknown> = {
      session: `S${i + 1}`,
      date: new Date(date).toLocaleDateString("it-IT"),
    };
    KEY_METRICS.forEach(metric => {
      if (report.trends[metric]) {
        row[metric] = report.trends[metric].values[i];
      }
    });
    return row;
  });

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Analisi Longitudinale</h1>
        <p style={styles.subtitle}>
          Paziente: <strong>{report.patient_code}</strong> · {report.n_sessions} sessioni · {report.span_days} giorni
        </p>
      </div>

      <div style={styles.summaryCard}>
        <p style={styles.summaryText}>{report.summary}</p>
      </div>

      {report.alerts.length > 0 && (
        <div style={styles.alertsCard}>
          <h3 style={styles.alertsTitle}>⚠ Alert clinici ({report.alerts.length})</h3>
          {report.alerts.map((alert, i) => (
            <div key={i} style={styles.alertRow}>{alert}</div>
          ))}
        </div>
      )}

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>Trend metriche principali</h3>
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey="session" />
            <YAxis domain={[0, 100]} />
            <Tooltip
              labelFormatter={(label, payload) => {
                const row = payload[0]?.payload;
                return row ? `${label} (${row.date})` : label;
              }}
            />
            <Legend />
            <Line
              type="monotone" dataKey="overall_cognitive_score"
              name="Score complessivo" stroke="#2E5C8A" strokeWidth={3}
            />
            <Line type="monotone" dataKey="cpt_attention_score"
                  name="CPT Attention" stroke="#43A047" />
            <Line type="monotone" dataKey="digit_span_fine_grained"
                  name="Digit Span" stroke="#FB8C00" />
            <Line type="monotone" dataKey="stroop_cw_accuracy"
                  name="Stroop CW" stroke="#8E24AA" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={styles.card}>
        <h3 style={styles.cardTitle}>Tabella trend completa</h3>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Metrica</th>
              <th style={styles.th}>Valori</th>
              <th style={styles.th}>Δ%</th>
              <th style={styles.th}>Trend</th>
              <th style={styles.th}>RCI</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(report.trends).map(([name, trend], i) => (
              <tr key={name} style={{
                background: i % 2 === 0 ? "white" : "#F0F4F8",
              }}>
                <td style={styles.td}>{name}</td>
                <td style={styles.td}>
                  {trend.values.map(v => v.toFixed(1)).join(" → ")}
                </td>
                <td style={{
                  ...styles.td,
                  color: trend.change_pct > 0 ? "#43A047" : "#E53935",
                  fontWeight: "bold",
                }}>
                  {trend.change_pct > 0 ? "+" : ""}{trend.change_pct.toFixed(1)}%
                </td>
                <td style={{
                  ...styles.td,
                  color: DIRECTION_COLOR[trend.direction],
                  fontWeight: "bold",
                }}>
                  {DIRECTION_ICON[trend.direction]} {trend.direction}
                </td>
                <td style={styles.td}>
                  {trend.rci_value.toFixed(2)}
                  {trend.reliable_change && (
                    <span style={styles.significantBadge}>significativo</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: "1200px", margin: "0 auto", padding: "2rem",
    fontFamily: "system-ui, sans-serif",
  },
  header: { marginBottom: "2rem" },
  title: { margin: 0, color: "#2E5C8A", fontSize: "1.8rem" },
  subtitle: { color: "#6C757D", margin: "0.3rem 0 0 0" },
  summaryCard: {
    background: "#D5E8F0", padding: "1rem 1.5rem", borderRadius: "8px",
    marginBottom: "1rem",
  },
  summaryText: { margin: 0, fontSize: "0.95rem", lineHeight: 1.5 },
  alertsCard: {
    background: "#FFEBEE", padding: "1rem 1.5rem", borderRadius: "8px",
    border: "2px solid #E53935", marginBottom: "1.5rem",
  },
  alertsTitle: {
    margin: "0 0 0.75rem 0", color: "#E53935", fontSize: "1.05rem",
  },
  alertRow: {
    padding: "0.3rem 0", fontSize: "0.9rem",
  },
  card: {
    background: "#f8f9fa", padding: "1.5rem", borderRadius: "12px",
    border: "1px solid #dee2e6", marginBottom: "1.5rem",
  },
  cardTitle: {
    margin: "0 0 1rem 0", color: "#2E5C8A", fontSize: "1.05rem",
  },
  table: {
    width: "100%", borderCollapse: "collapse", fontSize: "0.85rem",
  },
  th: {
    textAlign: "left", padding: "0.6rem", background: "#2E5C8A",
    color: "white",
  },
  td: { padding: "0.6rem" },
  significantBadge: {
    display: "inline-block", marginLeft: "0.5rem",
    padding: "0.15rem 0.5rem", background: "#E53935",
    color: "white", borderRadius: "4px", fontSize: "0.7rem",
  },
};
