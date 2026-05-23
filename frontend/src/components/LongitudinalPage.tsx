/**
 * LongitudinalPage — analisi del trend di un paziente su più sessioni.
 * Seleziona un paziente, carica tutti i suoi report, li manda al backend
 * per l'analisi longitudinale, visualizza i trend con LongitudinalChart.
 */

import { useEffect, useState } from "react";
import {
  analyzeLongitudinal,
  getPatientReports,
  listPatients,
  Patient,
  SessionReportData,
} from "../api/client";
import { Card, Button, Badge, Icon, EmptyState } from "./ui";
import { colors, font, radius } from "../styles/theme";
import { LongitudinalChart } from "./LongitudinalChart";

export function LongitudinalPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientId, setPatientId] = useState<string | null>(null);
  const [reports, setReports] = useState<SessionReportData[]>([]);
  const [longReport, setLongReport] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listPatients().then(setPatients).catch(() => {});
  }, []);

  useEffect(() => {
    if (!patientId) {
      setReports([]);
      setLongReport(null);
      return;
    }
    (async () => {
      setLoading(true);
      setError(null);
      setLongReport(null);
      try {
        const rs = await getPatientReports(patientId);
        setReports(rs);
        if (rs.length >= 2) {
          const lr = await analyzeLongitudinal(rs);
          setLongReport(lr);
        }
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        setError(
          err.response?.data?.detail ||
            err.message ||
            "Errore caricamento dati longitudinali"
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [patientId]);

  const selected = patients.find((p) => p.id === patientId) || null;

  return (
    <div>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ marginBottom: "0.25rem" }}>Analisi longitudinale</h1>
        <p style={{ margin: 0, color: colors.muted, maxWidth: 720 }}>
          Valuta l'andamento cognitivo di un paziente nel tempo. Serve almeno due
          sessioni completate, idealmente a distanza di settimane o mesi.
        </p>
      </header>

      <Card title="Seleziona paziente" accent style={{ marginBottom: "1.25rem" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "0.75rem", alignItems: "center" }}>
          <select
            value={patientId || ""}
            onChange={(e) => setPatientId(e.target.value || null)}
            style={selectStyle}
          >
            <option value="">— Seleziona un paziente —</option>
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.external_code} · {p.age} anni
              </option>
            ))}
          </select>
          {selected && (
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <Badge>{reports.length} sessioni con report</Badge>
            </div>
          )}
        </div>
      </Card>

      {loading && (
        <Card>
          <div style={{ padding: "1rem", color: colors.muted }}>
            Caricamento report paziente e calcolo del trend…
          </div>
        </Card>
      )}

      {error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            background: colors.riskSoft,
            color: colors.risk,
            borderRadius: radius.md,
          }}
        >
          {error}
        </div>
      )}

      {!loading && patientId && reports.length === 0 && (
        <EmptyState
          icon="trend"
          title="Nessuna sessione con report"
          description="Questo paziente non ha ancora sessioni completate con punteggi. Avvia almeno una sessione, falla completare dal paziente, poi torna qui."
        />
      )}

      {!loading && reports.length === 1 && (
        <EmptyState
          icon="trend"
          title="Una sola sessione disponibile"
          description="L'analisi longitudinale richiede almeno due sessioni per calcolare un trend. Al momento ne è presente solo una."
        />
      )}

      {!loading && reports.length >= 2 && longReport && (
        <>
          {/* Timeline sessioni */}
          <Card title="Sessioni incluse nell'analisi" style={{ marginBottom: "1.25rem" }}>
            <SessionTimeline reports={reports} />
          </Card>

          {/* Grafico trend */}
          <LongitudinalChart report={longReport as Parameters<typeof LongitudinalChart>[0]["report"]} />
        </>
      )}
    </div>
  );
}

function SessionTimeline({ reports }: { reports: SessionReportData[] }) {
  return (
    <div style={{ display: "flex", gap: "0.5rem", overflowX: "auto", paddingBottom: "0.5rem" }}>
      {reports.map((r, i) => {
        const riskColor = r.overall_risk_level === "low"
          ? colors.accent
          : r.overall_risk_level === "medium"
            ? colors.warn
            : colors.risk;
        return (
          <div
            key={r.session_id}
            style={{
              flex: "0 0 auto",
              minWidth: 180,
              padding: "0.85rem 1rem",
              border: `1px solid ${colors.border}`,
              borderLeft: `3px solid ${riskColor}`,
              borderRadius: radius.md,
              background: colors.surface,
            }}
          >
            <div style={{ fontSize: "0.72rem", color: colors.muted, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Sessione {i + 1}
            </div>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: "1.1rem", marginTop: "0.2rem", color: colors.ink }}>
              {r.overall_cognitive_score.toFixed(1)}
              <span style={{ fontSize: "0.8rem", color: colors.muted, fontWeight: 400 }}>/100</span>
            </div>
            <div style={{ fontSize: "0.82rem", color: colors.muted, marginTop: "0.25rem" }}>
              {new Date(r.session_date).toLocaleDateString("it-IT", {
                day: "2-digit", month: "short", year: "numeric",
              })}
            </div>
            <div style={{ marginTop: "0.5rem" }}>
              <Badge tone={r.overall_risk_level === "low" ? "accent" : r.overall_risk_level === "medium" ? "warn" : "risk"}>
                {r.overall_risk_level}
              </Badge>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.5rem 0.75rem",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  fontSize: "0.95rem",
  background: "#fff",
};
