/**
 * NewSessionPage — wizard a 3 step per creare una sessione:
 *   1. Scelta paziente (esistente o nuovo)
 *   2. Selezione e configurazione dei test
 *   3. Generazione + link di esecuzione
 */

import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import {
  buildSession,
  createPatient,
  listPatients,
  Patient,
  SessionResponse,
  TestConfigInput,
} from "../api/client";
import { Card, Button, Badge, Icon } from "./ui";
import { colors, font, radius, shadow } from "../styles/theme";

type TestType = "CPT" | "DigitSpan" | "Stroop" | "GoNoGo" | "Narrative";

const DEFAULT_CLINICIAN = "dr_default";

// ============ default config per test ============
// Questi valori rispecchiano i default dei Config Pydantic del backend.
// Il medico può regolare quelli più rilevanti nell'UI.

const TEST_META: Record<TestType, { title: string; description: string; duration: string }> = {
  CPT: {
    title: "CPT — Continuous Performance Test",
    description: "Attenzione sostenuta e controllo dell'impulsività. Il paziente preme un tasto al comparire di una lettera target.",
    duration: "~14 minuti",
  },
  DigitSpan: {
    title: "Digit Span",
    description: "Memoria di lavoro verbale. Il paziente ascolta e ripete sequenze di cifre (diretto o inverso).",
    duration: "~5 minuti",
  },
  Stroop: {
    title: "Stroop Color-Word",
    description: "Controllo dell'interferenza e flessibilità cognitiva. Tre blocchi: parola, colore, parola-colore.",
    duration: "~4 minuti",
  },
  GoNoGo: {
    title: "Go/No-Go",
    description: "Inibizione della risposta. Fase di formazione, differenziazione e inversione delle regole.",
    duration: "~6 minuti",
  },
  Narrative: {
    title: "Narrative — Produzione verbale",
    description: "Il paziente descrive un'immagine o racconta (es. la giornata perfetta). La risposta vocale o testuale alimenta l'analisi multi-canale.",
    duration: "~3 minuti",
  },
};

function defaultConfig(t: TestType): Record<string, unknown> {
  switch (t) {
    case "CPT":
      return {
        target_letter: "X",
        total_duration_minutes: 14,
        target_ratio: 0.10,
        stimulus_duration_ms: 250,
        isi_min_ms: 1000,
        isi_max_ms: 4000,
        alphabet: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
      };
    case "DigitSpan":
      return {
        mode: "forward",
        start_length: 3,
        max_length: 8,
        sequences_per_level: 2,
        stop_after_failures: 2,
        inter_digit_interval_ms: 1000,
        tts_voice: "female",
        tts_language: "it",
      };
    case "Stroop":
      return {
        language: "it",
        colors: ["rosso", "verde", "blu", "giallo"],
        conditions: ["word", "color", "color_word"],
        items_per_block: 100,
        block_duration_seconds: 45,
        response_mode: "click",
        congruent_ratio_in_cw: 0.0,
      };
    case "GoNoGo":
      return {
        go_color: "red",
        nogo_color: "yellow",
        include_formation: true,
        include_reverse: true,
        trials_per_phase: 20,
        stimulus_duration_min_ms: 200,
        stimulus_duration_max_ms: 1100,
        isi_min_ms: 1300,
        isi_max_ms: 7500,
        response_feedback: false,
      };
    case "Narrative":
      return {
        prompt_type: "perfect_day",   // picture_description | perfect_day | daily_routine | story_retell
        language: "it",
        response_mode: "text",        // 'text' di default: robusto anche senza Whisper
        min_response_seconds: 30,
        min_words: 25,
        image_ref: null,              // obbligatorio solo se prompt_type = picture_description
        run_multichannel: true,
      };
  }
}

// ============ COMPONENT ============

export function NewSessionPage() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedPatient = searchParams.get("patient");

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientId, setPatientId] = useState<string | null>(preselectedPatient);
  const [showNewPatient, setShowNewPatient] = useState(false);
  const [newPatient, setNewPatient] = useState({
    external_code: "",
    age: 65,
    language: "it",
    education_years: undefined as number | undefined,
    clinical_suspicion: "none",
  });

  const [selectedTests, setSelectedTests] = useState<Map<TestType, Record<string, unknown>>>(
    new Map([["CPT", defaultConfig("CPT")]])
  );
  const [notes, setNotes] = useState("");

  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<SessionResponse | null>(null);

  useEffect(() => {
    listPatients().then(setPatients).catch(() => {});
  }, []);

  const selectedPatient = useMemo(
    () => patients.find((p) => p.id === patientId) || null,
    [patients, patientId]
  );

  const toggleTest = (t: TestType) => {
    const next = new Map(selectedTests);
    if (next.has(t)) next.delete(t);
    else next.set(t, defaultConfig(t));
    setSelectedTests(next);
  };

  const updateConfig = (t: TestType, patch: Record<string, unknown>) => {
    const next = new Map(selectedTests);
    const cur = next.get(t) || {};
    next.set(t, { ...cur, ...patch });
    setSelectedTests(next);
  };

  const handleCreatePatientAndNext = async () => {
    setError(null);
    if (!newPatient.external_code.trim()) {
      setError("Codice paziente obbligatorio.");
      return;
    }
    try {
      const p = await createPatient({
        ...newPatient,
        clinical_suspicion:
          newPatient.clinical_suspicion === "none" ? null : newPatient.clinical_suspicion,
      } as Partial<Patient>);
      setPatients([p, ...patients]);
      setPatientId(p.id);
      setShowNewPatient(false);
      setStep(2);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail || "Errore creazione paziente");
    }
  };

  const handleBuild = async () => {
    if (!patientId || selectedTests.size === 0) return;
    setError(null);
    setBuilding(true);
    try {
      const tests: TestConfigInput[] = Array.from(selectedTests.entries()).map(
        ([test_type, config], i) => ({ test_type, order: i, config })
      );
      const resp = await buildSession({
        patient_id: patientId,
        clinician_id: DEFAULT_CLINICIAN,
        tests,
        notes: notes || undefined,
      });
      setCreated(resp);
      setStep(3);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Errore durante la generazione della sessione"
      );
    } finally {
      setBuilding(false);
    }
  };

  return (
    <div>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ marginBottom: "0.25rem" }}>Nuova sessione</h1>
        <p style={{ margin: 0, color: colors.muted }}>
          Configura una batteria di test diagnostici per un paziente.
        </p>
      </header>

      <Stepper step={step} />

      {error && (
        <div
          style={{
            padding: "0.75rem 1rem",
            background: colors.riskSoft,
            color: colors.risk,
            borderRadius: radius.md,
            marginBottom: "1rem",
          }}
        >
          {error}
        </div>
      )}

      {/* STEP 1 — paziente */}
      {step === 1 && (
        <Card title="Seleziona il paziente" accent>
          {!showNewPatient ? (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "0.75rem", alignItems: "center", marginBottom: "1rem" }}>
                <select
                  value={patientId || ""}
                  onChange={(e) => setPatientId(e.target.value || null)}
                  style={inputStyle}
                >
                  <option value="">— Seleziona paziente esistente —</option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.external_code} · {p.age} anni
                      {p.clinical_suspicion && p.clinical_suspicion !== "none"
                        ? ` · sospetto ${p.clinical_suspicion}`
                        : ""}
                    </option>
                  ))}
                </select>
                <Button variant="secondary" onClick={() => setShowNewPatient(true)}>
                  <Icon name="plus" size={14} /> Nuovo
                </Button>
              </div>

              {selectedPatient && (
                <div
                  style={{
                    padding: "1rem",
                    background: colors.surface2,
                    borderRadius: radius.md,
                    border: `1px solid ${colors.border}`,
                  }}
                >
                  <PatientSummary patient={selectedPatient} />
                </div>
              )}
            </>
          ) : (
            <div style={{ display: "grid", gap: "1rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <Field label="Codice paziente*">
                  <input
                    type="text"
                    value={newPatient.external_code}
                    onChange={(e) => setNewPatient({ ...newPatient, external_code: e.target.value })}
                    placeholder="es. PAT002"
                    style={inputStyle}
                  />
                </Field>
                <Field label="Età">
                  <input
                    type="number"
                    min={5}
                    max={120}
                    value={newPatient.age}
                    onChange={(e) =>
                      setNewPatient({ ...newPatient, age: parseInt(e.target.value) || 0 })
                    }
                    style={inputStyle}
                  />
                </Field>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
                <Field label="Lingua">
                  <select
                    value={newPatient.language}
                    onChange={(e) => setNewPatient({ ...newPatient, language: e.target.value })}
                    style={inputStyle}
                  >
                    <option value="it">Italiano</option>
                    <option value="en">English</option>
                  </select>
                </Field>
                <Field label="Anni di istruzione">
                  <input
                    type="number"
                    min={0}
                    max={30}
                    value={newPatient.education_years ?? ""}
                    onChange={(e) =>
                      setNewPatient({
                        ...newPatient,
                        education_years: e.target.value ? parseInt(e.target.value) : undefined,
                      })
                    }
                    style={inputStyle}
                  />
                </Field>
                <Field label="Sospetto clinico">
                  <select
                    value={newPatient.clinical_suspicion}
                    onChange={(e) =>
                      setNewPatient({ ...newPatient, clinical_suspicion: e.target.value })
                    }
                    style={inputStyle}
                  >
                    <option value="none">Nessuno</option>
                    <option value="MCI">MCI</option>
                    <option value="Alzheimer">Alzheimer</option>
                    <option value="ADHD">ADHD</option>
                    <option value="Parkinson">Parkinson</option>
                  </select>
                </Field>
              </div>
              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                <Button variant="ghost" onClick={() => setShowNewPatient(false)}>
                  Annulla
                </Button>
                <Button onClick={handleCreatePatientAndNext}>Crea e continua</Button>
              </div>
            </div>
          )}

          {!showNewPatient && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1rem" }}>
              <Button onClick={() => setStep(2)} disabled={!patientId}>
                Continua <Icon name="arrow" size={14} />
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* STEP 2 — test */}
      {step === 2 && selectedPatient && (
        <>
          <Card title="Paziente selezionato" bodyStyle={{ padding: "1rem 1.25rem" }} style={{ marginBottom: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <PatientSummary patient={selectedPatient} inline />
              <Button variant="ghost" size="sm" onClick={() => setStep(1)}>
                Cambia
              </Button>
            </div>
          </Card>

          <Card title="Batteria di test" subtitle="Seleziona i test e regola i parametri clinici." accent>
            <div style={{ display: "grid", gap: "0.75rem" }}>
              {(Object.keys(TEST_META) as TestType[]).map((t) => {
                const active = selectedTests.has(t);
                return (
                  <div
                    key={t}
                    style={{
                      border: `1px solid ${active ? colors.ink2 : colors.border}`,
                      borderRadius: radius.lg,
                      background: active ? colors.surface : colors.surface2,
                      overflow: "hidden",
                      transition: "border-color 160ms, background 160ms",
                    }}
                  >
                    <div
                      style={{
                        padding: "0.9rem 1.1rem",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: "1rem",
                        cursor: "pointer",
                      }}
                      onClick={() => toggleTest(t)}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                        <div
                          style={{
                            width: 20, height: 20,
                            border: `2px solid ${active ? colors.ink2 : colors.borderStrong}`,
                            background: active ? colors.ink2 : "transparent",
                            borderRadius: 4,
                            display: "grid",
                            placeItems: "center",
                            color: "#fff",
                          }}
                        >
                          {active && <Icon name="check" size={12} strokeWidth={3} />}
                        </div>
                        <div>
                          <div style={{ fontFamily: font.display, fontWeight: 600, color: colors.ink }}>
                            {TEST_META[t].title}
                          </div>
                          <div style={{ fontSize: "0.85rem", color: colors.muted, marginTop: "0.15rem" }}>
                            {TEST_META[t].description}
                          </div>
                        </div>
                      </div>
                      <Badge tone="sky">{TEST_META[t].duration}</Badge>
                    </div>

                    {active && (
                      <div
                        style={{
                          padding: "1rem 1.1rem",
                          borderTop: `1px solid ${colors.border}`,
                          background: colors.surface2,
                        }}
                      >
                        <TestConfigEditor
                          type={t}
                          config={selectedTests.get(t) || {}}
                          onChange={(patch) => updateConfig(t, patch)}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div style={{ marginTop: "1.25rem" }}>
              <Field label="Note cliniche (opzionali)">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder="Indicazioni, sintomi riferiti, motivazione della valutazione…"
                  style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }}
                />
              </Field>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "1.5rem" }}>
              <Button variant="ghost" onClick={() => setStep(1)}>← Indietro</Button>
              <Button onClick={handleBuild} disabled={selectedTests.size === 0 || building}>
                {building ? "Generazione stimoli in corso…" : `Genera sessione (${selectedTests.size} test)`}
              </Button>
            </div>
          </Card>

          {building && (
            <div
              style={{
                marginTop: "1rem",
                padding: "1rem",
                background: colors.skySoft,
                border: `1px solid #BAE6FD`,
                borderRadius: radius.md,
                color: colors.sky,
                fontSize: "0.9rem",
              }}
            >
              L'LLM sta generando gli stimoli per ogni test selezionato. Può richiedere
              <strong> 20–60 secondi </strong>
              a seconda del numero di test e del modello configurato.
            </div>
          )}
        </>
      )}

      {/* STEP 3 — risultato */}
      {step === 3 && created && (
        <Card title="Sessione generata" accent>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
            <div
              style={{
                width: 32, height: 32,
                background: colors.accentSoft,
                color: "#065F46",
                borderRadius: "50%",
                display: "grid",
                placeItems: "center",
              }}
            >
              <Icon name="check" size={18} strokeWidth={2.5} />
            </div>
            <div>
              <div style={{ fontFamily: font.display, fontWeight: 600, color: colors.ink }}>
                Sessione pronta all'esecuzione
              </div>
              <div style={{ color: colors.muted, fontSize: "0.88rem" }}>
                Condividi il link con il paziente. Potrà eseguirla da qualunque browser.
              </div>
            </div>
          </div>

          <LinkBlock sessionId={created.id} />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginTop: "1.25rem" }}>
            <InfoPill label="ID sessione" value={created.id.substring(0, 8) + "…"} mono />
            <InfoPill label="Stato" value={created.status} />
            <InfoPill label="N. test generati" value={String(created.test_configs.length)} />
            <InfoPill
              label="Stimoli totali"
              value={String(created.test_configs.reduce((a, c) => a + (c.stimulus_count || 0), 0))}
            />
          </div>

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <Button onClick={() => nav("/sessions")}>Vai all'elenco sessioni</Button>
            <Button variant="secondary" onClick={() => { setStep(1); setCreated(null); setSelectedTests(new Map([["CPT", defaultConfig("CPT")]])); }}>
              Crea un'altra
            </Button>
            <Link to={`/run/${created.id}`}>
              <Button variant="ghost">Apri modalità paziente →</Button>
            </Link>
          </div>
        </Card>
      )}
    </div>
  );
}

// ============ Editor config per test ============

function TestConfigEditor({
  type,
  config,
  onChange,
}: {
  type: TestType;
  config: Record<string, unknown>;
  onChange: (patch: Record<string, unknown>) => void;
}) {
  if (type === "CPT") {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
        <Field label="Lettera target">
          <input
            type="text"
            maxLength={1}
            value={String(config.target_letter || "X")}
            onChange={(e) => onChange({ target_letter: e.target.value.toUpperCase() })}
            style={inputStyle}
          />
        </Field>
        <Field label="Durata (min)">
          <input
            type="number"
            min={5}
            max={30}
            value={Number(config.total_duration_minutes) || 14}
            onChange={(e) => onChange({ total_duration_minutes: parseInt(e.target.value) || 14 })}
            style={inputStyle}
          />
        </Field>
        <Field label="Ratio target">
          <input
            type="number"
            step="0.05"
            min={0.05}
            max={0.5}
            value={Number(config.target_ratio) || 0.1}
            onChange={(e) => onChange({ target_ratio: parseFloat(e.target.value) || 0.1 })}
            style={inputStyle}
          />
        </Field>
      </div>
    );
  }
  if (type === "DigitSpan") {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem" }}>
        <Field label="Modalità">
          <select
            value={String(config.mode || "forward")}
            onChange={(e) => onChange({ mode: e.target.value })}
            style={inputStyle}
          >
            <option value="forward">Forward</option>
            <option value="backward">Backward</option>
          </select>
        </Field>
        <Field label="Lunghezza iniziale">
          <input
            type="number" min={2} max={5}
            value={Number(config.start_length) || 3}
            onChange={(e) => onChange({ start_length: parseInt(e.target.value) || 3 })}
            style={inputStyle}
          />
        </Field>
        <Field label="Lunghezza max">
          <input
            type="number" min={4} max={10}
            value={Number(config.max_length) || 8}
            onChange={(e) => onChange({ max_length: parseInt(e.target.value) || 8 })}
            style={inputStyle}
          />
        </Field>
        <Field label="Seq. per livello">
          <input
            type="number" min={1} max={4}
            value={Number(config.sequences_per_level) || 2}
            onChange={(e) => onChange({ sequences_per_level: parseInt(e.target.value) || 2 })}
            style={inputStyle}
          />
        </Field>
      </div>
    );
  }
  if (type === "Stroop") {
    const conds = (config.conditions as string[]) || ["word", "color", "color_word"];
    const toggleCond = (c: string) => {
      const next = conds.includes(c) ? conds.filter((x) => x !== c) : [...conds, c];
      onChange({ conditions: next.length > 0 ? next : conds });
    };
    return (
      <div style={{ display: "grid", gap: "0.75rem" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
          <Field label="Items per blocco">
            <input
              type="number" min={20} max={200}
              value={Number(config.items_per_block) || 100}
              onChange={(e) => onChange({ items_per_block: parseInt(e.target.value) || 100 })}
              style={inputStyle}
            />
          </Field>
          <Field label="Durata blocco (sec)">
            <input
              type="number" min={30} max={120}
              value={Number(config.block_duration_seconds) || 45}
              onChange={(e) => onChange({ block_duration_seconds: parseInt(e.target.value) || 45 })}
              style={inputStyle}
            />
          </Field>
          <Field label="Modalità risposta">
            <select
              value={String(config.response_mode || "click")}
              onChange={(e) => onChange({ response_mode: e.target.value })}
              style={inputStyle}
            >
              <option value="click">Click</option>
              <option value="vocal">Vocale</option>
            </select>
          </Field>
        </div>
        <Field label="Blocchi attivi">
          <div style={{ display: "flex", gap: "0.5rem", paddingTop: "0.15rem" }}>
            {(["word", "color", "color_word"] as const).map((c) => (
              <label
                key={c}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.35rem 0.7rem",
                  border: `1px solid ${conds.includes(c) ? colors.ink2 : colors.border}`,
                  borderRadius: radius.pill,
                  fontSize: "0.82rem",
                  cursor: "pointer",
                  background: conds.includes(c) ? colors.skySoft : "transparent",
                }}
              >
                <input
                  type="checkbox"
                  checked={conds.includes(c)}
                  onChange={() => toggleCond(c)}
                  style={{ margin: 0 }}
                />
                {c}
              </label>
            ))}
          </div>
        </Field>
      </div>
    );
  }
  if (type === "GoNoGo") {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem" }}>
        <Field label="Colore Go">
          <select
            value={String(config.go_color || "red")}
            onChange={(e) => onChange({ go_color: e.target.value })}
            style={inputStyle}
          >
            <option value="red">Red</option>
            <option value="green">Green</option>
            <option value="blue">Blue</option>
            <option value="yellow">Yellow</option>
          </select>
        </Field>
        <Field label="Colore No-Go">
          <select
            value={String(config.nogo_color || "yellow")}
            onChange={(e) => onChange({ nogo_color: e.target.value })}
            style={inputStyle}
          >
            <option value="red">Red</option>
            <option value="green">Green</option>
            <option value="blue">Blue</option>
            <option value="yellow">Yellow</option>
          </select>
        </Field>
        <Field label="Trial per fase">
          <input
            type="number" min={15} max={30}
            value={Number(config.trials_per_phase) || 20}
            onChange={(e) => onChange({ trials_per_phase: parseInt(e.target.value) || 20 })}
            style={inputStyle}
          />
        </Field>
        <Field label="Fase inversa">
          <select
            value={config.include_reverse ? "1" : "0"}
            onChange={(e) => onChange({ include_reverse: e.target.value === "1" })}
            style={inputStyle}
          >
            <option value="1">Inclusa</option>
            <option value="0">Esclusa</option>
          </select>
        </Field>
      </div>
    );
  }
  return null;
}

// ============ Helpers UI ============

function Stepper({ step }: { step: 1 | 2 | 3 }) {
  const labels = ["Paziente", "Test", "Sessione"];
  return (
    <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
      {labels.map((l, i) => {
        const n = (i + 1) as 1 | 2 | 3;
        const active = step >= n;
        return (
          <div key={l} style={{ flex: 1, display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div
              style={{
                width: 28, height: 28,
                borderRadius: "50%",
                background: active ? colors.ink2 : colors.surface3,
                color: active ? "#fff" : colors.muted,
                display: "grid",
                placeItems: "center",
                fontSize: "0.82rem",
                fontWeight: 600,
                fontFamily: font.mono,
                flexShrink: 0,
              }}
            >
              {n}
            </div>
            <div style={{ fontSize: "0.9rem", color: active ? colors.ink : colors.muted, fontWeight: active ? 500 : 400 }}>
              {l}
            </div>
            {i < 2 && (
              <div style={{ flex: 1, height: 1, background: colors.border, marginLeft: "0.5rem" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function PatientSummary({ patient, inline }: { patient: Patient; inline?: boolean }) {
  const items: Array<[string, string]> = [
    ["Codice", patient.external_code],
    ["Età", `${patient.age} anni`],
    ["Lingua", patient.language.toUpperCase()],
  ];
  if (patient.clinical_suspicion && patient.clinical_suspicion !== "none") {
    items.push(["Sospetto", patient.clinical_suspicion]);
  }
  if (patient.education_years != null) {
    items.push(["Istruzione", `${patient.education_years} anni`]);
  }
  return (
    <div style={{ display: "flex", gap: inline ? "1.5rem" : "2rem", flexWrap: "wrap" }}>
      {items.map(([k, v]) => (
        <div key={k}>
          <div
            style={{
              fontSize: "0.7rem",
              color: colors.muted,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {k}
          </div>
          <div style={{ fontSize: "0.95rem", color: colors.ink, fontWeight: 500, marginTop: "0.1rem", fontFamily: k === "Codice" ? font.mono : undefined }}>
            {v}
          </div>
        </div>
      ))}
    </div>
  );
}

function LinkBlock({ sessionId }: { sessionId: string }) {
  const url = `${window.location.origin}/run/${sessionId}`;
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  return (
    <div
      style={{
        padding: "0.85rem 1rem",
        background: colors.surface2,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1rem",
      }}
    >
      <code
        style={{
          fontFamily: font.mono,
          fontSize: "0.88rem",
          color: colors.ink,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {url}
      </code>
      <Button size="sm" variant="secondary" onClick={copy}>
        <Icon name="copy" size={14} /> {copied ? "Copiato!" : "Copia link"}
      </Button>
    </div>
  );
}

function InfoPill({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div
      style={{
        padding: "0.6rem 0.8rem",
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        background: colors.surface,
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          color: colors.muted,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "0.92rem",
          color: colors.ink,
          fontWeight: 500,
          marginTop: "0.15rem",
          fontFamily: mono ? font.mono : undefined,
        }}
      >
        {value}
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
          fontSize: "0.72rem",
          color: colors.muted,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "0.3rem",
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.45rem 0.7rem",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  fontSize: "0.92rem",
  background: "#fff",
};
