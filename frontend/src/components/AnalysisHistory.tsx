/**
 * AnalysisHistory — consulta le analisi multi-canale salvate in DB.
 *
 * Elenca le analisi (piu' recenti prima) con i tre indici e i canali usati;
 * cliccando una riga si apre il dettaglio completo (trascrizione + features).
 * Opzionale: passa una sessionId per filtrare solo quella sessione.
 */

import { useEffect, useState } from "react";
import { getAnalysisResults, getAnalysisResult } from "../api/client";

interface AnalysisSummary {
  id: string;
  session_id: string | null;
  created_at: string | null;
  cognitive_strain_index: number | null;
  emotional_distress_index: number | null;
  communication_quality_index: number | null;
  channels_available: string[];
  transcript: string | null;
}

interface Props {
  sessionId?: string; // se passato, filtra per sessione
}

export function AnalysisHistory({ sessionId }: Props) {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getAnalysisResults(sessionId);
        setItems(data);
      } catch (e: any) {
        setError(e?.message || "Errore nel caricamento");
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionId]);

  const toggle = async (id: string) => {
    if (openId === id) { setOpenId(null); setDetail(null); return; }
    setOpenId(id);
    setDetail(null);
    try {
      setDetail(await getAnalysisResult(id));
    } catch {
      setDetail({ error: "Impossibile caricare il dettaglio" });
    }
  };

  if (loading) return <div style={s.wrap}>Caricamento analisi…</div>;
  if (error) return <div style={s.wrap}><div style={s.err}>{error}</div></div>;

  return (
    <div style={s.wrap}>
      <h2 style={s.h2}>Analisi multi-canale salvate</h2>
      {items.length === 0 && <p style={{ color: "#777" }}>Nessuna analisi salvata.</p>}

      {items.map((it) => (
        <div key={it.id} style={s.card}>
          <div style={s.row} onClick={() => toggle(it.id)}>
            <div style={{ flex: 1 }}>
              <div style={s.date}>
                {it.created_at ? new Date(it.created_at).toLocaleString("it-IT") : "—"}
                {it.session_id && <span style={s.sess}> · sessione {it.session_id.slice(0, 8)}</span>}
              </div>
              <div style={s.snippet}>{it.transcript?.slice(0, 90) || "—"}…</div>
            </div>
            <div style={s.indices}>
              <Metric label="Strain" value={it.cognitive_strain_index} />
              <Metric label="Distress" value={it.emotional_distress_index} />
              <Metric label="Quality" value={it.communication_quality_index} />
            </div>
          </div>

          <div style={s.channels}>
            {(it.channels_available || []).map((c) => (
              <span key={c} style={s.badge}>{c}</span>
            ))}
          </div>

          {openId === it.id && (
            <div style={s.detail}>
              {!detail ? "Caricamento dettaglio…" : (
                <>
                  <div style={s.transcriptFull}>{detail.features?.transcript}</div>
                  <pre style={s.pre}>{JSON.stringify(detail.features, null, 2)}</pre>
                </>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | null }) {
  const v = value ?? 0;
  const color = v >= 66 ? "#C62828" : v >= 33 ? "#EF6C00" : "#43A047";
  return (
    <div style={s.metric}>
      <div style={{ ...s.metricVal, color }}>{value == null ? "—" : v.toFixed(0)}</div>
      <div style={s.metricLbl}>{label}</div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  wrap: { maxWidth: 820, margin: "2rem auto", padding: "0 1rem", fontFamily: "system-ui, sans-serif" },
  h2: { fontSize: "1.4rem", marginBottom: "1rem" },
  card: { border: "1px solid #e0e0e0", borderRadius: 10, marginBottom: "0.75rem", overflow: "hidden" },
  row: { display: "flex", alignItems: "center", gap: "1rem", padding: "0.9rem 1rem", cursor: "pointer" },
  date: { fontSize: "0.8rem", color: "#888" },
  sess: { color: "#aaa" },
  snippet: { fontSize: "0.95rem", color: "#333", marginTop: 2 },
  indices: { display: "flex", gap: "1.2rem" },
  metric: { textAlign: "center", minWidth: 52 },
  metricVal: { fontSize: "1.25rem", fontWeight: 700 },
  metricLbl: { fontSize: "0.7rem", color: "#999", textTransform: "uppercase" },
  channels: { display: "flex", gap: 6, padding: "0 1rem 0.7rem" },
  badge: { fontSize: "0.72rem", background: "#eef2ff", color: "#3949ab", padding: "2px 8px", borderRadius: 12 },
  detail: { borderTop: "1px solid #eee", padding: "1rem", background: "#fafafa" },
  transcriptFull: { fontStyle: "italic", color: "#444", marginBottom: "0.8rem", lineHeight: 1.5 },
  pre: { fontSize: "0.75rem", background: "#fff", border: "1px solid #eee", borderRadius: 6, padding: "0.75rem", overflowX: "auto", maxHeight: 320 },
  err: { padding: "0.75rem", background: "#f8d7da", color: "#721c24", borderRadius: 8 },
};
