/**
 * PatientsPage — lista pazienti, creazione rapida, ricerca.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createPatient, listPatients, Patient } from "../api/client";
import { Card, Button, Badge, Icon, EmptyState } from "./ui";
import { colors, font, radius } from "../styles/theme";

export function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const nav = useNavigate();

  const reload = async () => {
    setLoading(true);
    try {
      const ps = await listPatients();
      setPatients(ps);
      setError(null);
    } catch (e: unknown) {
      setError((e as { message?: string })?.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) return patients;
    const q = query.toLowerCase();
    return patients.filter(
      (p) =>
        p.external_code.toLowerCase().includes(q) ||
        String(p.age).includes(q) ||
        (p.clinical_suspicion || "").toLowerCase().includes(q)
    );
  }, [patients, query]);

  return (
    <div>
      <header style={{ marginBottom: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>Pazienti</h1>
          <p style={{ margin: 0, color: colors.muted }}>
            {patients.length} pazienti registrati nel sistema.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Icon name="plus" size={16} /> Nuovo paziente
        </Button>
      </header>

      <Card bodyStyle={{ padding: 0 }}>
        <div style={{ padding: "1rem 1.25rem", borderBottom: `1px solid ${colors.border}` }}>
          <input
            type="search"
            placeholder="Cerca per codice, età, sospetto clinico…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "0.5rem 0.75rem",
              border: `1px solid ${colors.border}`,
              borderRadius: radius.md,
              fontSize: "0.92rem",
            }}
          />
        </div>

        {loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: colors.muted }}>
            Caricamento pazienti…
          </div>
        ) : error ? (
          <div style={{ padding: "1rem", color: colors.risk }}>Errore: {error}</div>
        ) : filtered.length === 0 && patients.length === 0 ? (
          <EmptyState
            icon="user"
            title="Nessun paziente registrato"
            description="Inizia creando il primo profilo anagrafico."
            action={
              <Button onClick={() => setShowCreate(true)}>
                <Icon name="plus" size={16} /> Crea paziente
              </Button>
            }
          />
        ) : filtered.length === 0 ? (
          <div style={{ padding: "2rem", textAlign: "center", color: colors.muted }}>
            Nessun paziente corrisponde alla ricerca.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: colors.surface3, fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.05em", color: colors.muted }}>
                <th style={th}>Codice</th>
                <th style={th}>Età</th>
                <th style={th}>Lingua</th>
                <th style={th}>Istruzione</th>
                <th style={th}>Sospetto clinico</th>
                <th style={th}>Registrato</th>
                <th style={th}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr
                  key={p.id}
                  style={{ borderTop: `1px solid ${colors.border}` }}
                >
                  <td style={td}>
                    <code style={{ fontFamily: font.mono, fontSize: "0.88rem", color: colors.ink }}>
                      {p.external_code}
                    </code>
                  </td>
                  <td style={td}>{p.age}</td>
                  <td style={td}>
                    <Badge>{p.language.toUpperCase()}</Badge>
                  </td>
                  <td style={td}>
                    {p.education_years != null ? `${p.education_years} anni` : "—"}
                  </td>
                  <td style={td}>
                    {p.clinical_suspicion ? (
                      <Badge tone={p.clinical_suspicion === "none" ? "neutral" : "warn"}>
                        {p.clinical_suspicion}
                      </Badge>
                    ) : (
                      <span style={{ color: colors.soft }}>—</span>
                    )}
                  </td>
                  <td style={td}>
                    <span style={{ color: colors.muted }}>
                      {new Date(p.created_at).toLocaleDateString("it-IT")}
                    </span>
                  </td>
                  <td style={{ ...td, textAlign: "right" }}>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => nav(`/sessions/new?patient=${p.id}`)}
                    >
                      Nuova sessione <Icon name="arrow" size={14} />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {showCreate && (
        <CreatePatientModal
          onClose={() => setShowCreate(false)}
          onCreated={async () => {
            setShowCreate(false);
            await reload();
          }}
        />
      )}
    </div>
  );
}

function CreatePatientModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    external_code: "",
    age: 65,
    language: "it",
    education_years: undefined as number | undefined,
    clinical_suspicion: "none",
    handedness: "right" as "right" | "left" | "ambidextrous",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setError(null);
    if (!form.external_code.trim()) {
      setError("Il codice paziente è obbligatorio.");
      return;
    }
    setSaving(true);
    try {
      await createPatient({
        ...form,
        clinical_suspicion:
          form.clinical_suspicion === "none" ? null : form.clinical_suspicion,
      } as Partial<Patient>);
      onCreated();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Errore durante la creazione.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={modalBackdrop} onClick={onClose}>
      <div style={modal} onClick={(e) => e.stopPropagation()}>
        <header style={modalHeader}>
          <h2 style={{ margin: 0 }}>Nuovo paziente</h2>
          <p style={{ margin: "0.25rem 0 0 0", color: colors.muted, fontSize: "0.88rem" }}>
            Il codice identifica univocamente il paziente. Nessun dato personale (nome, CF).
          </p>
        </header>

        <div style={{ padding: "1.25rem", display: "grid", gap: "1rem" }}>
          <Field label="Codice paziente*">
            <input
              type="text"
              value={form.external_code}
              placeholder="es. PAT001"
              onChange={(e) => setForm({ ...form, external_code: e.target.value })}
              style={inputStyle}
              autoFocus
            />
          </Field>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <Field label="Età">
              <input
                type="number"
                min={5}
                max={120}
                value={form.age}
                onChange={(e) => setForm({ ...form, age: parseInt(e.target.value) || 0 })}
                style={inputStyle}
              />
            </Field>

            <Field label="Lingua">
              <select
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
                style={inputStyle}
              >
                <option value="it">Italiano</option>
                <option value="en">English</option>
              </select>
            </Field>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <Field label="Anni di istruzione">
              <input
                type="number"
                min={0}
                max={30}
                value={form.education_years ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    education_years: e.target.value ? parseInt(e.target.value) : undefined,
                  })
                }
                style={inputStyle}
              />
            </Field>

            <Field label="Dominanza">
              <select
                value={form.handedness}
                onChange={(e) =>
                  setForm({ ...form, handedness: e.target.value as typeof form.handedness })
                }
                style={inputStyle}
              >
                <option value="right">Destra</option>
                <option value="left">Sinistra</option>
                <option value="ambidextrous">Ambidestra</option>
              </select>
            </Field>
          </div>

          <Field label="Sospetto clinico">
            <select
              value={form.clinical_suspicion}
              onChange={(e) => setForm({ ...form, clinical_suspicion: e.target.value })}
              style={inputStyle}
            >
              <option value="none">Nessuno</option>
              <option value="MCI">MCI — Mild Cognitive Impairment</option>
              <option value="Alzheimer">Alzheimer</option>
              <option value="ADHD">ADHD</option>
              <option value="Parkinson">Parkinson</option>
            </select>
          </Field>

          {error && (
            <div
              style={{
                padding: "0.6rem 0.8rem",
                background: colors.riskSoft,
                color: colors.risk,
                borderRadius: radius.md,
                fontSize: "0.88rem",
              }}
            >
              {error}
            </div>
          )}
        </div>

        <footer style={modalFooter}>
          <Button variant="ghost" onClick={onClose}>
            Annulla
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Salvataggio…" : "Crea paziente"}
          </Button>
        </footer>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block" }}>
      <span
        style={{
          display: "block",
          fontSize: "0.78rem",
          color: colors.muted,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "0.35rem",
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      {children}
    </label>
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
};
const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.5rem 0.75rem",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  fontSize: "0.95rem",
  background: "#fff",
};
const modalBackdrop: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(15, 31, 53, 0.45)",
  display: "grid",
  placeItems: "center",
  zIndex: 100,
  padding: "1rem",
};
const modal: React.CSSProperties = {
  background: "#fff",
  borderRadius: 12,
  maxWidth: 540,
  width: "100%",
  maxHeight: "90vh",
  overflowY: "auto",
  boxShadow: "0 20px 60px rgba(15, 31, 53, 0.25)",
};
const modalHeader: React.CSSProperties = {
  padding: "1.25rem",
  borderBottom: `1px solid ${colors.border}`,
};
const modalFooter: React.CSSProperties = {
  padding: "1rem 1.25rem",
  borderTop: `1px solid ${colors.border}`,
  display: "flex",
  justifyContent: "flex-end",
  gap: "0.5rem",
  background: colors.surface2,
};
