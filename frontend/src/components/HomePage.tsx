/**
 * Home — panoramica aggregata:
 * - statistiche (n. pazienti, n. sessioni per stato)
 * - ultime sessioni con accesso rapido al report
 * - distribuzione rischio
 */

import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  listPatients,
  listSessions,
  Patient,
  SessionListItem,
} from "../api/client";
import { Card, Button, Badge, Icon } from "./ui";
import { colors, font } from "../styles/theme";

export function HomePage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const [ps, ss] = await Promise.all([listPatients(), listSessions()]);
        setPatients(ps);
        setSessions(ss);
      } catch (e: unknown) {
        const msg = (e as { message?: string })?.message || String(e);
        setError(msg);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const scored = sessions.filter((s) => s.n_scored > 0);
  const ready = sessions.filter((s) => s.status === "ready" || s.status === "in_progress");
  const draft = sessions.filter((s) => s.status === "draft");

  return (
    <div>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ marginBottom: "0.25rem" }}>Panoramica clinica</h1>
        <p style={{ margin: 0, color: colors.muted }}>
          Vista d'insieme dell'attività diagnostica recente.
        </p>
      </header>

      {error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            background: colors.riskSoft,
            color: colors.risk,
            borderRadius: 6,
            marginBottom: "1rem",
          }}
        >
          Errore caricamento dati: {error}
        </div>
      )}

      {/* Metriche */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        <MetricCard label="Pazienti registrati" value={patients.length} />
        <MetricCard label="Sessioni totali" value={sessions.length} />
        <MetricCard label="Con punteggi" value={scored.length} accent />
        <MetricCard label="In attesa di esecuzione" value={ready.length + draft.length} />
      </div>

      {/* Azioni rapide */}
      <Card title="Azioni rapide" accent style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Button onClick={() => nav("/sessions/new")}>
            <Icon name="plus" size={16} /> Nuova sessione
          </Button>
          <Button variant="secondary" onClick={() => nav("/patients")}>
            <Icon name="user" size={16} /> Gestisci pazienti
          </Button>
          <Button variant="secondary" onClick={() => nav("/longitudinal")}>
            <Icon name="trend" size={16} /> Analisi longitudinale
          </Button>
          <Button variant="ghost" onClick={() => nav("/analyze")}>
            <Icon name="mic" size={16} /> Analisi multicanale singola
          </Button>
        </div>
      </Card>

      {/* Ultime sessioni */}
      <Card
        title="Ultime sessioni"
        subtitle={loading ? "Caricamento..." : `${sessions.length} sessioni totali`}
        right={
          <Link
            to="/sessions"
            style={{ color: colors.muted, fontSize: "0.88rem" }}
          >
            Vedi tutte →
          </Link>
        }
        bodyStyle={{ padding: 0 }}
      >
        {sessions.length === 0 && !loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: colors.muted }}>
            Nessuna sessione ancora creata.{" "}
            <Link to="/sessions/new" style={{ color: colors.ink2, fontWeight: 500 }}>
              Crea la prima
            </Link>.
          </div>
        ) : (
          <SessionTable sessions={sessions.slice(0, 8)} />
        )}
      </Card>
    </div>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div
      style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: 10,
        padding: "1.1rem 1.25rem",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {accent && (
        <div
          style={{
            position: "absolute",
            left: 0, top: 0, bottom: 0,
            width: 3,
            background: colors.accent,
          }}
        />
      )}
      <div
        style={{
          fontSize: "0.72rem",
          color: colors.muted,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: "0.5rem",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: font.display,
          fontSize: "2rem",
          fontWeight: 600,
          color: colors.ink,
          lineHeight: 1,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function SessionTable({ sessions }: { sessions: SessionListItem[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: colors.surface3, fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.05em", color: colors.muted }}>
            <th style={thStyle}>Paziente</th>
            <th style={thStyle}>Data</th>
            <th style={thStyle}>Test</th>
            <th style={thStyle}>Stato</th>
            <th style={thStyle}></th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.id} style={{ borderTop: `1px solid ${colors.border}` }}>
              <td style={tdStyle}>
                <code style={{ fontFamily: font.mono, fontSize: "0.85rem" }}>
                  {s.patient_code}
                </code>
                <span style={{ color: colors.muted, marginLeft: "0.5rem", fontSize: "0.82rem" }}>
                  {s.patient_age} anni
                </span>
              </td>
              <td style={tdStyle}>
                {new Date(s.created_at).toLocaleDateString("it-IT", {
                  day: "2-digit", month: "short", year: "numeric",
                })}
              </td>
              <td style={tdStyle}>
                <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
                  {s.test_types.map((t) => (
                    <Badge key={t}>{t}</Badge>
                  ))}
                </div>
              </td>
              <td style={tdStyle}>
                <StatusBadge status={s.status} scored={s.n_scored > 0} />
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                {s.n_scored > 0 ? (
                  <Link to={`/sessions/${s.id}/report`} style={linkCta}>
                    Report →
                  </Link>
                ) : (
                  <Link to={`/run/${s.id}`} style={{ ...linkCta, color: colors.muted }}>
                    Link paziente
                  </Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StatusBadge({ status, scored }: { status: string; scored?: boolean }) {
  if (scored) return <Badge tone="accent">Completata</Badge>;
  if (status === "ready") return <Badge tone="sky">Pronta</Badge>;
  if (status === "in_progress") return <Badge tone="warn">In corso</Badge>;
  if (status === "draft") return <Badge>Bozza</Badge>;
  return <Badge>{status}</Badge>;
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "0.7rem 1.25rem",
  fontWeight: 500,
};
const tdStyle: React.CSSProperties = {
  padding: "0.85rem 1.25rem",
  fontSize: "0.92rem",
};
const linkCta: React.CSSProperties = {
  color: colors.ink2,
  fontWeight: 500,
  fontSize: "0.88rem",
};
