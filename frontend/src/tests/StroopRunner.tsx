/**
 * StroopRunner — somministra il Color-Word test.
 *
 * Il paziente vede una parola stampata in un colore e deve cliccare
 * il pulsante corrispondente al colore dell'inchiostro (non alla parola letta).
 */

import { useState, useEffect, useRef } from "react";
import { PreciseTimer } from "../utils/timing";
import { ResponseItem, submitResponsesBatch } from "../api/client";

interface StroopStimulus {
  word: string;
  ink_color: string;
  condition: string;
}

interface StroopBlockData {
  condition: string;
  language: string;
  stimuli: StroopStimulus[];
}

interface Props {
  sessionId: string;
  testConfigId: string;
  stimulusId: string;
  data: StroopBlockData;
  onComplete: () => void;
}

type Screen = "instructions" | "running" | "complete";

// Palette
const COLOR_HEX: Record<string, string> = {
  rosso: "#E53935", red: "#E53935",
  verde: "#43A047", green: "#43A047",
  blu: "#1E88E5", blue: "#1E88E5",
  giallo: "#FDD835", yellow: "#FDD835",
  black: "#000000",
};

export function StroopRunner({
  sessionId, testConfigId, stimulusId, data, onComplete,
}: Props) {
  const [screen, setScreen] = useState<Screen>("instructions");
  const [currentIdx, setCurrentIdx] = useState(0);
  const timerRef = useRef(new PreciseTimer());
  const responsesRef = useRef<ResponseItem[]>([]);

  const currentStim = data.stimuli[currentIdx];
  const availableColors = Array.from(
    new Set(data.stimuli.map(s => s.ink_color).filter(c => c !== "black"))
  );

  // Avvia timer all'entrata nello stimolo
  useEffect(() => {
    if (screen === "running") timerRef.current.start();
  }, [screen, currentIdx]);

  const handleColorClick = async (color: string) => {
    if (screen !== "running") return;
    const rt = timerRef.current.elapsed();
    responsesRef.current.push({
      stimulus_id: stimulusId,
      session_id: sessionId,
      trial_index: currentIdx,
      response_type: "click",
      response_value: color,
      reaction_time_ms: rt,
    });

    if (currentIdx < data.stimuli.length - 1) {
      setCurrentIdx(i => i + 1);
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

  if (screen === "instructions") {
    return (
      <div style={styles.container}>
        <h2>Stroop Color-Word Test</h2>
        <div style={styles.instructions}>
          <p>Vedrai delle parole stampate in colori diversi.</p>
          <p>
            Clicca il pulsante che corrisponde al <strong>colore dell'inchiostro</strong>,
            NON alla parola letta.
          </p>
          <p>Esempio: se vedi la parola "rosso" scritta in <span style={{color: COLOR_HEX.blu}}>blu</span>,
            devi cliccare il pulsante <strong>blu</strong>.</p>
          <p>Sii il più rapido e preciso possibile.</p>
          <button style={styles.startButton} onClick={() => setScreen("running")}>
            Inizia
          </button>
        </div>
      </div>
    );
  }

  if (screen === "running" && currentStim) {
    return (
      <div style={styles.container}>
        <div style={{
          ...styles.word,
          color: COLOR_HEX[currentStim.ink_color] || currentStim.ink_color,
        }}>
          {currentStim.word}
        </div>
        <div style={styles.buttonsRow}>
          {availableColors.map(color => (
            <button
              key={color}
              style={{
                ...styles.colorButton,
                background: COLOR_HEX[color] || color,
              }}
              onClick={() => handleColorClick(color)}
            >
              {color}
            </button>
          ))}
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
  word: {
    fontSize: "8rem", fontWeight: "bold", fontFamily: "Arial, sans-serif",
    marginBottom: "4rem",
  },
  buttonsRow: { display: "flex", gap: "1rem", flexWrap: "wrap", justifyContent: "center" },
  colorButton: {
    padding: "1.5rem 3rem", fontSize: "1.3rem", fontWeight: "bold",
    color: "white", border: "none", borderRadius: "8px", cursor: "pointer",
    textTransform: "capitalize", textShadow: "1px 1px 2px rgba(0,0,0,0.5)",
  },
  startButton: {
    marginTop: "2rem", padding: "1rem 3rem", fontSize: "1.2rem",
    background: "#2e5c8a", color: "white", border: "none",
    borderRadius: "8px", cursor: "pointer",
  },
  progress: {
    position: "fixed", bottom: "1rem", right: "1rem",
    fontSize: "0.9rem", color: "#888",
  },
};
