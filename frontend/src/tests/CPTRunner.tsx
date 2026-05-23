/**
 * CPTRunner — componente che somministra il Continuous Performance Test.
 *
 * Flusso:
 * 1. Mostra istruzioni
 * 2. Countdown di 3 secondi
 * 3. Per ogni stimolo: mostra per stimulus_duration_ms, raccoglie risposta
 *    durante lo stimolo + ISI, registra RT preciso
 * 4. Al termine: invia batch di risposte al backend
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { preciseSleep, PreciseTimer } from "../utils/timing";
import { ResponseItem, submitResponsesBatch } from "../api/client";

interface CPTStimulus {
  stimulus: string;
  is_target: boolean;
  isi_ms: number;
}

interface CPTData {
  target_letter: string;
  stimuli: CPTStimulus[];
}

interface Props {
  sessionId: string;
  testConfigId: string;
  stimulusId: string;
  data: CPTData;
  stimulusDurationMs?: number;
  onComplete: () => void;
}

type Phase = "instructions" | "countdown" | "running" | "complete";

export function CPTRunner({
  sessionId,
  testConfigId,
  stimulusId,
  data,
  stimulusDurationMs = 250,
  onComplete,
}: Props) {
  const [phase, setPhase] = useState<Phase>("instructions");
  const [currentStim, setCurrentStim] = useState<string | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [countdown, setCountdown] = useState(3);

  // Refs per timing: evitiamo re-render che invalidano il timing
  const timerRef = useRef(new PreciseTimer());
  const respondedRef = useRef(false);
  const responsesRef = useRef<ResponseItem[]>([]);
  const stoppedRef = useRef(false);

  // Handler keypress globale durante il test
  const handleKeyPress = useCallback((ev: KeyboardEvent) => {
    if (ev.key !== " " || respondedRef.current) return;
    respondedRef.current = true;
    const rt = timerRef.current.elapsed();

    // Registra la risposta (associata all'indice corrente)
    responsesRef.current.push({
      stimulus_id: stimulusId,
      session_id: sessionId,
      trial_index: currentIdx,
      response_type: "key",
      response_value: "space",
      reaction_time_ms: rt,
    });
  }, [stimulusId, sessionId, currentIdx]);

  // Attiva/disattiva listener
  useEffect(() => {
    if (phase === "running") {
      window.addEventListener("keydown", handleKeyPress);
      return () => window.removeEventListener("keydown", handleKeyPress);
    }
  }, [phase, handleKeyPress]);

  // Countdown
  useEffect(() => {
    if (phase !== "countdown") return;
    if (countdown === 0) {
      setPhase("running");
      return;
    }
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [phase, countdown]);

  // Loop principale del test
  useEffect(() => {
    if (phase !== "running") return;
    stoppedRef.current = false;

    const runLoop = async () => {
      for (let i = 0; i < data.stimuli.length; i++) {
        if (stoppedRef.current) return;

        const stim = data.stimuli[i];
        setCurrentIdx(i);
        respondedRef.current = false;

        // Mostra stimolo
        setCurrentStim(stim.stimulus);
        timerRef.current.start();
        await preciseSleep(stimulusDurationMs);

        // Nasconde stimolo, ma continua a raccogliere risposte durante ISI
        setCurrentStim(null);
        await preciseSleep(stim.isi_ms);

        // Se non ha risposto entro la finestra, registra "none"
        if (!respondedRef.current) {
          responsesRef.current.push({
            stimulus_id: stimulusId,
            session_id: sessionId,
            trial_index: i,
            response_type: "none",
            response_value: null,
            reaction_time_ms: null,
          });
        }
      }

      // Fine test: invia batch
      setPhase("complete");
      try {
        await submitResponsesBatch({
          session_id: sessionId,
          test_config_id: testConfigId,
          responses: responsesRef.current,
        });
        setTimeout(onComplete, 1500);
      } catch (e) {
        console.error("Errore submit risposte:", e);
      }
    };

    runLoop();
    return () => { stoppedRef.current = true; };
  }, [phase, data.stimuli, stimulusDurationMs, sessionId, testConfigId, stimulusId, onComplete]);

  // ============ RENDER ============
  if (phase === "instructions") {
    return (
      <div style={styles.container}>
        <h2>Continuous Performance Test</h2>
        <div style={styles.instructions}>
          <p>Guarderai una sequenza di lettere sullo schermo.</p>
          <p>
            Premi la <strong>barra spaziatrice</strong> ogni volta che vedi
            la lettera <strong style={styles.targetLetter}>{data.target_letter}</strong>.
          </p>
          <p>Non premere nulla per le altre lettere.</p>
          <p>Sii il più rapido e preciso possibile.</p>
          <button style={styles.startButton} onClick={() => setPhase("countdown")}>
            Inizia
          </button>
        </div>
      </div>
    );
  }

  if (phase === "countdown") {
    return (
      <div style={styles.container}>
        <div style={styles.countdown}>{countdown > 0 ? countdown : "Via!"}</div>
      </div>
    );
  }

  if (phase === "running") {
    return (
      <div style={styles.container}>
        <div style={styles.stimulus}>
          {currentStim || <span style={{ opacity: 0.1 }}>+</span>}
        </div>
        <div style={styles.progress}>
          {currentIdx + 1} / {data.stimuli.length}
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <h2>Test completato</h2>
      <p>Elaborazione dei risultati in corso...</p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "80vh",
    fontFamily: "system-ui, sans-serif",
    userSelect: "none",
  },
  instructions: {
    maxWidth: "600px",
    textAlign: "center",
    fontSize: "1.1rem",
    lineHeight: 1.6,
  },
  targetLetter: {
    fontSize: "1.5rem",
    color: "#2e5c8a",
    padding: "0 0.3rem",
  },
  startButton: {
    marginTop: "2rem",
    padding: "1rem 3rem",
    fontSize: "1.2rem",
    background: "#2e5c8a",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
  },
  countdown: {
    fontSize: "10rem",
    fontWeight: "bold",
    color: "#2e5c8a",
  },
  stimulus: {
    fontSize: "16rem",
    fontWeight: "bold",
    color: "#222",
    fontFamily: "monospace",
    height: "18rem",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  progress: {
    position: "fixed",
    bottom: "1rem",
    right: "1rem",
    fontSize: "0.9rem",
    color: "#888",
  },
};
