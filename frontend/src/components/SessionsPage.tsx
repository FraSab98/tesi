/**
 * SessionsPage — elenco sessioni con filtro per stato.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listSessions, SessionListItem } from "../api/client";
import { Card, Button, Badge, Icon, EmptyState } from "./ui";
import { colors, font, radius } from "../styles/theme";
import { StatusBadge } from "./HomePage";

type Filter = "all" | "scored" | "ready" | "draft";

export function SessionsPage() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const ss = await listSessions();
        setSessions(ss);
      } catch (e: unknown) {
        setError((e as { message?: string })?.message || String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const visible = useMemo(() => {
    let arr = sessions;
    if (filter === "scored") arr = arr.filter((s) => s.n_scored > 0);
    if (filter === "ready") arr = arr.filter((s) => s.status === "ready" || s.status === "in_progress");
    if (filter === "draft") arr = arr.filter((s) => s.status === "draft");
    if (query.trim()) {
      const q = query.toLowerCase();
      arr = arr.filter(
        (s) =>
          s.patient_code.toLowerCase().includes(q) ||
          s.test_types.some((t) => t.toLowerCase().includes(q))
      );
    }
    return arr;
  }, [sessions, filter, query]);

  const counts = useMemo(() => ({
    all: sessions.length,
    scored: sessions.filter((s) => s.n_scored > 0).length,
    ready: sessions.filter((s) => s.status === "ready" || s.status === "in_progress").length,
    draft: sessions.filter((s) => s.status === "draft").length,
  }), [sessions]);

  return (
    <div>
      <header style={{ marginBottom: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>Sessioni</h1>
          <p style={{ margin: 0, color: colors.muted }}>
            Tutte le sessioni diagnostiche, filtrabili per stato.
          </p>
        </div>
        <Button onClick={() => nav("/sessions/new")}>
          <Icon name="plus" size={16} /> Nuova sessione
        </Button>
      </header>

      <Card bodyStyle={{ padding: 0 }}>
        <div style={{ padding: "1rem 1.25rem", borderBottom: `1px solid ${colors.border}`, display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: "0.35rem" }}>
            <FilterTab label="Tutte"     active={filter === "all"}    count={counts.all}    onClick={() => setFilter("all")} />
            <FilterTab label="Con report" active={filter === "scored"} count={counts.scored} onClick={() => setFilter("scored")} />
            <FilterTab label="In esecuzione" active={filter === "ready"} count={counts.ready} onClick={() => setFilter("ready")} />
            <FilterTab label="Bozze"     active={filter === "draft"}  count={counts.draft}  onClick={() => setFilter("draft")} />
          </div>
          <div style={{ flex: 1, minWidth: 220 }}>
            <input
              type="search"
              placeholder="Filtra per codice paziente o test…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{
                width: "100%",
                padding: "0.4rem 0.7rem",
                border: `1px solid ${colors.border}`,
                borderRadius: radius.md,
                fontSize: "0.9rem",
              }}
            />
          </div>
        </div>

        {loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: colors.muted }}>
            Caricamento sessioni…
          </div>
        ) : error ? (
          <div style={{ padding: "1rem", color: colors.risk }}>Errore: {error}</div>
        ) : visible.length === 0 && sessions.length === 0 ? (
          <EmptyState
            icon="clipboard"
            title="Nessuna sessione creata"
            description="Crea una nuova sessione assegnando una batteria di test a un paziente."
            action={
              <Button onClick={() => nav("/sessions/new")}>
                <Icon name="plus" size={16} /> Crea sessione
              </Button>
            }
          />
        ) : visible.length === 0 ? (
          <div style={{ padding: "2rem", textAlign: "center", color: colors.muted }}>
            Nessuna sessione corrisponde al filtro.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: colors.surface3, fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.05em", color: colors.muted }}>
                <th style={th}>Paziente</th>
                <th style={th}>Data</th>
                <th style={th}>Test</th>
                <th style={th}>Stato</th>
                <th style={th}>Note</th>
                <th style={th}></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((s) => (
                <tr key={s.id} style={{ borderTop: `1px solid ${colors.border}` }}>
                  <td style={td}>
                    <code style={{ fontFamily: font.mono, fontSize: "0.88rem", color: colors.ink }}>
                      {s.patient_code}
                    </code>
                    <span style={{ color: colors.muted, marginLeft: "0.5rem", fontSize: "0.82rem" }}>
                      {s.patient_age} anni
                    </span>
                  </td>
                  <td style={td}>
                    {new Date(s.created_at).toLocaleDateString("it-IT", {
                      day: "2-digit", month: "short", year: "numeric",
                    })}
                    <div style={{ fontSize: "0.78rem", color: colors.muted }}>
                      {new Date(s.created_at).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}
                    </div>
                  </td>
                  <td style={td}>
                    <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
                      {s.test_types.map((t) => (
                        <Badge key={t}>{t}</Badge>
                      ))}
                    </div>
                    <div style={{ fontSize: "0.78rem", color: colors.muted, marginTop: "0.25rem" }}>
                      {s.n_scored}/{s.n_tests} punteggi
                    </div>
                  </td>
                  <td style={td}>
                    <StatusBadge status={s.status} scored={s.n_scored > 0 || s.n_analyses > 0} />
                  </td>
                  <td style={{ ...td, maxWidth: 200 }}>
                    <span style={{ color: s.notes ? colors.body : colors.soft, fontSize: "0.88rem" }}>
                      {s.notes || "—"}
                    </span>
                  </td>
                  <td style={{ ...td, textAlign: "right" }}>
                    <div style={{ display: "flex", gap: "0.25rem", justifyContent: "flex-end" }}>
                      {(s.n_scored > 0 || s.n_analyses > 0) && (
                        <Link to={`/sessions/${s.id}/report`}>
                          <Button size="sm" variant="secondary">
                            Report <Icon name="arrow" size={14} />
                          </Button>
                        </Link>
                      )}
                      {(s.n_scored === 0 && s.n_analyses === 0) && (
                        <Link to={`/run/${s.id}`}>
                          <Button size="sm" variant="ghost">
                            Link paziente
                          </Button>
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function FilterTab({
  label,
  active,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "0.35rem 0.85rem",
        border: "1px solid transparent",
        borderRadius: radius.pill,
        background: active ? colors.ink2 : colors.surface3,
        color: active ? "#fff" : colors.body,
        fontSize: "0.85rem",
        fontWeight: 500,
        cursor: "pointer",
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
      }}
    >
      {label}
      <span
        style={{
          fontSize: "0.78rem",
          color: active ? "rgba(255,255,255,0.75)" : colors.muted,
          fontFamily: font.mono,
        }}
      >
        {count}
      </span>
    </button>
  );
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "0.7rem 1.25rem",
  fontWeight: 500,
};
const td: React.CSSProperties = {
  padding: "0.85rem 1.25rem",
  fontSize: "0.92rem",
  verticalAlign: "top",
};
