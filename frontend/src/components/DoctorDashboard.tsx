/**
 * DoctorDashboard — interfaccia per il medico.
 *
 * Permette di:
 * 1. Creare un paziente (o selezionarne uno esistente)
 * 2. Configurare la batteria di test (test scelti + parametri)
 * 3. Avviare la generazione della sessione (gli stimoli vengono generati dall'LLM)
 * 4. Ottenere il link/token da condividere col paziente
 */

import { useState } from "react";
import {
  createPatient,
  buildSession,
  SessionResponse,
  TestConfigInput,
} from "../api/client";

export function DoctorDashboard() {
  const [externalCode, setExternalCode] = useState("PAT001");
  const [age, setAge] = useState(65);
  const [language, setLanguage] = useState("it");
  const [selectedTests, setSelectedTests] = useState<Set<string>>(new Set(["CPT"]));
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdSession, setCreatedSession] = useState<SessionResponse | null>(null);

  const toggleTest = (t: string) => {
    const next = new Set(selectedTests);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    setSelectedTests(next);
  };

  const handleCreateSession = async () => {
    setError(null);
    setBuilding(true);
    try {
      // Crea paziente
      const patient = await createPatient({
        external_code: externalCode,
        age,
        language,
      });

      // Costruisci lista test con config default
      const tests: TestConfigInput[] = [];
      let order = 0;

      if (selectedTests.has("CPT")) {
        tests.push({
          test_type: "CPT",
          order: order++,
          config: {
            target_letter: "X",
            total_duration_minutes: 5,  // MVP: ridotto
            target_ratio: 0.15,
            stimulus_duration_ms: 250,
            isi_min_ms: 1000,
            isi_max_ms: 2500,
          },
        });
      }

      if (selectedTests.has("DigitSpan")) {
        tests.push({
          test_type: "DigitSpan",
          order: order++,
          config: {
            mode: "forward",
            start_length: 4,
            max_length: 7,
            sequences_per_level: 2,
            tts_language: language,
          },
        });
      }

      if (selectedTests.has("Stroop")) {
        tests.push({
          test_type: "Stroop",
          order: order++,
          config: {
            language,
            colors: ["rosso", "verde", "blu", "giallo"],
            conditions: ["color_word"],
            items_per_block: 20,  // MVP: ridotto
            block_duration_seconds: 45,
            response_mode: "click",
          },
        });
      }

      if (selectedTests.has("GoNoGo")) {
        tests.push({
          test_type: "GoNoGo",
          order: order++,
          config: {
            go_color: "#43A047",
            nogo_color: "#E53935",
            include_formation: true,
            include_reverse: false,  // MVP: senza reverse
            trials_per_phase: 20,
          },
        });
      }

      if (tests.length === 0) {
        setError("Seleziona almeno un test");
        setBuilding(false);
        return;
      }

      const session = await buildSession({
        patient_id: patient.id,
        clinician_id: "DR001",
        tests,
      });

      setCreatedSession(session);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || "Errore");
    } finally {
      setBuilding(false);
    }
  };

  if (createdSession) {
    const runUrl = `${window.location.origin}/run/${createdSession.id}`;
    return (
      <div style={styles.container}>
        <h2>✓ Sessione creata</h2>
        <div style={styles.card}>
          <p><strong>ID sessione:</strong> {createdSession.id}</p>
          <p><strong>Status:</strong> {createdSession.status}</p>
          <p><strong>Test configurati:</strong> {createdSession.test_configs.length}</p>
          <ul>
            {createdSession.test_configs.map(tc => (
              <li key={tc.id}>
                {tc.test_type} — {tc.stimulus_count ?? "?"} stimoli generati
              </li>
            ))}
          </ul>
          <hr />
          <p><strong>Link per il paziente:</strong></p>
          <a href={runUrl} style={styles.link}>{runUrl}</a>
          <div style={{ marginTop: "2rem" }}>
            <button
              style={styles.button}
              onClick={() => window.location.href = runUrl}
            >
              Avvia sessione ora
            </button>
            <button
              style={styles.buttonSecondary}
              onClick={() => setCreatedSession(null)}
            >
              Crea un'altra sessione
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <h1>Piattaforma di valutazione cognitiva</h1>
      <h2>Nuova sessione</h2>

      <div style={styles.card}>
        <h3>Paziente</h3>
        <label style={styles.label}>
          Codice paziente:
          <input
            type="text"
            value={externalCode}
            onChange={e => setExternalCode(e.target.value)}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Età:
          <input
            type="number"
            value={age}
            onChange={e => setAge(parseInt(e.target.value) || 0)}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Lingua:
          <select value={language} onChange={e => setLanguage(e.target.value)} style={styles.input}>
            <option value="it">Italiano</option>
            <option value="en">English</option>
          </select>
        </label>
      </div>

      <div style={styles.card}>
        <h3>Batteria di test</h3>
        <p>Seleziona i test da somministrare:</p>
        {["CPT", "DigitSpan", "Stroop", "GoNoGo"].map(t => (
          <label key={t} style={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={selectedTests.has(t)}
              onChange={() => toggleTest(t)}
            />
            <span>{t}</span>
          </label>
        ))}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      <button
        style={{ ...styles.button, opacity: building ? 0.6 : 1 }}
        onClick={handleCreateSession}
        disabled={building}
      >
        {building ? "Generazione stimoli in corso..." : "Crea sessione"}
      </button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: "800px", margin: "0 auto", padding: "2rem",
    fontFamily: "system-ui, sans-serif",
  },
  card: {
    background: "#f8f9fa", padding: "1.5rem", borderRadius: "8px",
    marginBottom: "1.5rem", border: "1px solid #dee2e6",
  },
  label: { display: "block", marginBottom: "1rem" },
  input: {
    display: "block", width: "100%", padding: "0.5rem",
    marginTop: "0.3rem", fontSize: "1rem",
    border: "1px solid #ced4da", borderRadius: "4px",
  },
  checkboxLabel: {
    display: "flex", alignItems: "center", gap: "0.5rem",
    padding: "0.5rem", fontSize: "1.1rem",
  },
  button: {
    padding: "1rem 2rem", fontSize: "1.1rem", background: "#2e5c8a",
    color: "white", border: "none", borderRadius: "8px", cursor: "pointer",
    marginRight: "1rem",
  },
  buttonSecondary: {
    padding: "1rem 2rem", fontSize: "1.1rem", background: "#6c757d",
    color: "white", border: "none", borderRadius: "8px", cursor: "pointer",
  },
  error: {
    padding: "1rem", background: "#f8d7da", color: "#721c24",
    borderRadius: "4px", marginBottom: "1rem",
  },
  link: { color: "#2e5c8a", wordBreak: "break-all" },
};
