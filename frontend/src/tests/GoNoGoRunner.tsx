/**
 * GoNoGoRunner — somministra il Go/No-Go task.
 *
 * Durante ogni trial viene mostrato un cerchio colorato. Il paziente deve
 * cliccare (risposta Go) o NON cliccare (risposta NoGo) in base al colore
 * della fase corrente.
 */

import { useState, useEffect, useRef } from "react";
import { preciseSleep, PreciseTimer } from "../utils/timing";
import { ResponseItem, submitResponsesBatch } from "../api/client";

interface Trial {
  stimulus_type: "go" | "nogo";
  stimulus_color: string;
  stimulus_duration_ms: number;
  isi_ms: number;
}

interface Phase {
  phase: string;
  go_stimulus_color: string;
  nogo_stimulus_color: string;
  trials: Trial[];
}

interface GoNoGoData {
  phases: Phase[];
}

interface Props {
  sessionId: string;
  testConfigId: string;
  stimulusId: string;
  data: GoNoGoData;
  onComplete: () => void;
}

type Screen = "instructions" | "phase-intro" | "countdown" | "running" | "complete";

export function GoNoGoRunner({
  sessionId, testConfigId, stimulusId, data, onComplete,
}: Props) {
  const [screen, setScreen] = useState<Screen>("instructions");
  const [currentPhaseIdx, setCurrentPhaseIdx] = useState(0);
  const [currentStim, setCurrentStim] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(3);
  const [trialIdx, setTrialIdx] = useState(0);

  const timerRef = useRef(new PreciseTimer());
  const respondedRef = useRef(false);
  const responsesRef = useRef<ResponseItem[]>([]);
  const globalIdxRef = useRef(0);
  const stoppedRef = useRef(false);

  const currentPhase = data.phases[currentPhaseIdx];

  // Handler globale: accetta click del mouse E barra spaziatrice
  useEffect(() => {
    if (screen !== "running") return;

    const registerResponse = (source: "click" | "key") => {
      if (respondedRef.current) return;
      respondedRef.current = true;
      const rt = timerRef.current.elapsed();
      responsesRef.current.push({
        stimulus_id: stimulusId,
        session_id: sessionId,
        trial_index: globalIdxRef.current,
        response_type: source === "click" ? "click" : "key",
        response_value: source === "click" ? "clicked" : "space",
        reaction_time_ms: rt,
      });
    };

    const handleClick = () => registerResponse("click");
    const handleKey = (e: KeyboardEvent) => {
      // Accetta barra spaziatrice ed Enter (evita che lo spazio scrolli la pagina)
      if (e.code === "Space" || e.key === " " || e.key === "Enter") {
        e.preventDefault();
        registerResponse("key");
      }
    };

    window.addEventListener("click", handleClick);
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("click", handleClick);
      window.removeEventListener("keydown", handleKey);
    };
  }, [screen, stimulusId, sessionId]);

  // Countdown
  useEffect(() => {
    if (screen !== "countdown") return;
    if (countdown === 0) {
      setScreen("running");
      setCountdown(3);
      return;
    }
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [screen, countdown]);

  // Loop trials della fase corrente
  useEffect(() => {
    if (screen !== "running") return;
    stoppedRef.current = false;

    const runPhase = async () => {
      const trials = currentPhase.trials;

      for (let i = 0; i < trials.length; i++) {
        if (stoppedRef.current) return;
        const trial = trials[i];
        setTrialIdx(i);
        respondedRef.current = false;

        // Mostra stimolo
        setCurrentStim(trial.stimulus_color);
        timerRef.current.start();
        await preciseSleep(trial.stimulus_duration_ms);

        // ISI (stimolo nascosto)
        setCurrentStim(null);
        await preciseSleep(trial.isi_ms);

        if (!respondedRef.current) {
          responsesRef.current.push({
            stimulus_id: stimulusId,
            session_id: sessionId,
            trial_index: globalIdxRef.current,
            response_type: "none",
            response_value: null,
            reaction_time_ms: null,
          });
        }
        globalIdxRef.current++;
      }

      // Passa alla prossima fase o completa
      if (currentPhaseIdx < data.phases.length - 1) {
        setCurrentPhaseIdx(i => i + 1);
        setScreen("phase-intro");
      } else {
        setScreen("complete");
        try {
          await submitResponsesBatch({
            session_id: sessionId,
            test_config_id: testConfigId,
            responses: responsesRef.current,
          });
          setTimeout(onComplete, 1500);
        } catch (e) {
          console.error("Errore submit:", e);
        }
      }
    };

    runPhase();
    return () => { stoppedRef.current = true; };
  }, [screen, currentPhaseIdx, data.phases, currentPhase, sessionId, testConfigId, stimulusId, onComplete]);

  // ============ RENDER ============
  if (screen === "instructions") {
    return (
      <div style={styles.container}>
        <h2>Go/No-Go Task</h2>
        <div style={styles.instructions}>
          <p>Vedrai cerchi colorati apparire sullo schermo.</p>
          <p>
            Dovrai <strong>rispondere</strong> o <strong>NON rispondere</strong> in base al colore.
          </p>
          <p style={{ marginTop: "1.5rem", padding: "0.9rem 1rem", background: "#F1F5F9", borderRadius: 8 }}>
            <strong>Come rispondere:</strong> premi la <strong>barra spaziatrice</strong> sulla tastiera,
            oppure <strong>clicca</strong> con il mouse in un punto qualsiasi dello schermo.
          </p>
          <p>Le regole cambieranno a ogni fase: leggi bene le istruzioni prima di ogni fase.</p>
          <button style={styles.button} onClick={() => setScreen("phase-intro")}>
            Continua
          </button>
        </div>
      </div>
    );
  }

  if (screen === "phase-intro") {
    const phaseLabels: Record<string, string> = {
      formation: "Fase 1 — Addestramento",
      differentiation: "Fase 2 — Test",
      reverse_differentiation: "Fase 3 — Regole invertite",
    };
    return (
      <div style={styles.container}>
        <h2>{phaseLabels[currentPhase.phase] || currentPhase.phase}</h2>
        <div style={styles.instructions}>
          <p>In questa fase:</p>
          <div style={{ display: "flex", gap: "2rem", margin: "2rem 0", justifyContent: "center" }}>
            <div style={styles.ruleBox}>
              <div style={{ ...styles.circle, background: currentPhase.go_stimulus_color }} />
              <p><strong>RISPONDI</strong> (spazio o click)</p>
            </div>
            {currentPhase.phase !== "formation" && (
              <div style={styles.ruleBox}>
                <div style={{ ...styles.circle, background: currentPhase.nogo_stimulus_color }} />
                <p><strong>NON rispondere</strong> (attendi)</p>
              </div>
            )}
          </div>
          <button style={styles.button} onClick={() => setScreen("countdown")}>
            Inizia questa fase
          </button>
        </div>
      </div>
    );
  }  

  if (screen === "countdown") {
    return (
      <div style={styles.container}>
        <div style={styles.countdown}>{countdown > 0 ? countdown : "Via!"}</div>
      </div>
    );
  }

  if (screen === "running") {
    return (
      <div style={styles.container}>
        {currentStim ? (
          <div style={{ ...styles.stimulusCircle, background: currentStim }} />
        ) : (
          <div style={styles.fixation}>+</div>
        )}
        <div style={styles.progress}>
          Fase {currentPhaseIdx + 1}/{data.phases.length} — Trial {trialIdx + 1}/{currentPhase.trials.length}
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <h2>Test completato</h2>
      <p>Elaborazione in corso...</p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex", flexDirection: "column", alignItems: "center",
    justifyContent: "center", minHeight: "80vh",
    fontFamily: "system-ui, sans-serif", userSelect: "none",
  },
  instructions: {
    maxWidth: "600px", textAlign: "center", fontSize: "1.1rem", lineHeight: 1.6,
  },
  button: {
    marginTop: "2rem", padding: "1rem 3rem", fontSize: "1.2rem",
    background: "#2e5c8a", color: "white", border: "none",
    borderRadius: "8px", cursor: "pointer",
  },
  countdown: { fontSize: "10rem", fontWeight: "bold", color: "#2e5c8a" },
  stimulusCircle: {
    width: "250px", height: "250px", borderRadius: "50%",
    boxShadow: "0 4px 20px rgba(0,0,0,0.2)",
  },
  fixation: { fontSize: "4rem", color: "#ccc" },
  ruleBox: { textAlign: "center" },
  circle: {
    width: "100px", height: "100px", borderRadius: "50%", margin: "0 auto 1rem",
  },
  progress: {
    position: "fixed", bottom: "1rem", right: "1rem",
    fontSize: "0.9rem", color: "#888",
  },
};
