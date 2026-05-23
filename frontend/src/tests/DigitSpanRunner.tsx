/**
 * DigitSpanRunner — somministra il Digit Span test.
 *
 * Per ogni sequenza:
 * 1. Riproduce la sequenza usando Web Speech Synthesis (TTS)
 * 2. Registra la risposta vocale del paziente con MediaRecorder
 * 3. Invia l'audio al backend (che poi lo trascriverà con Whisper)
 *
 * In questo MVP usiamo una modalità semplificata: input testuale invece
 * del vocale, per poter testare il flusso end-to-end senza Whisper.
 */

import { useState, useEffect, useRef } from "react";
import { ResponseItem, submitResponsesBatch } from "../api/client";

interface DigitSequence {
  sequence: number[];
  length: number;
}

interface DigitSpanData {
  mode: string;
  sequences: DigitSequence[];
}

interface Props {
  sessionId: string;
  testConfigId: string;
  stimulusId: string;
  data: DigitSpanData;
  onComplete: () => void;
}

type Screen = "instructions" | "playing" | "responding" | "complete";

export function DigitSpanRunner({
  sessionId, testConfigId, stimulusId, data, onComplete,
}: Props) {
  const [screen, setScreen] = useState<Screen>("instructions");
  const [currentIdx, setCurrentIdx] = useState(0);
  const [currentDigit, setCurrentDigit] = useState<number | null>(null);
  const [userInput, setUserInput] = useState("");
  const responsesRef = useRef<ResponseItem[]>([]);

  const currentSeq = data.sequences[currentIdx];

  // Presenta la sequenza (visivamente + audio TTS)
  useEffect(() => {
    if (screen !== "playing" || !currentSeq) return;

    let cancelled = false;
    const playSequence = async () => {
      for (const digit of currentSeq.sequence) {
        if (cancelled) return;
        setCurrentDigit(digit);
        // TTS opzionale (fallback silenzioso se non supportato)
        if ("speechSynthesis" in window) {
          const utter = new SpeechSynthesisUtterance(digit.toString());
          utter.lang = "it-IT";
          utter.rate = 0.9;
          window.speechSynthesis.speak(utter);
        }
        await new Promise(r => setTimeout(r, 1000));
        setCurrentDigit(null);
        await new Promise(r => setTimeout(r, 250));
      }
      if (!cancelled) setScreen("responding");
    };
    playSequence();
    return () => { cancelled = true; };
  }, [screen, currentSeq]);

  const handleSubmitResponse = async () => {
    // Parse input: accetta sia "3 8 1 5" sia "3815"
    const digits = userInput
      .replace(/\s+/g, " ")
      .trim()
      .split(/\s+|/)
      .map(s => parseInt(s, 10))
      .filter(n => !isNaN(n));

    // Se il paziente ha scritto "3815" senza spazi, splittiamo per cifra
    let responseValue: string;
    if (digits.length === 1 && userInput.replace(/\s/g, "").length > 1) {
      const chars = userInput.replace(/\s/g, "").split("");
      responseValue = chars.join(" ");
    } else {
      responseValue = digits.join(" ");
    }

    // Per backward: il paziente ha detto la sequenza invertita.
    // Nello scoring backend memorizziamo la risposta come il paziente l'ha detta.
    // Il confronto avviene contro il target ruotato nel backend.

    responsesRef.current.push({
      stimulus_id: stimulusId,
      session_id: sessionId,
      trial_index: currentIdx,
      response_type: "vocal",  // in MVP è text, ma concettualmente simulia vocale
      response_value: responseValue,
      reaction_time_ms: null,  // non misurato nel MVP testuale
    });

    setUserInput("");

    if (currentIdx < data.sequences.length - 1) {
      setCurrentIdx(i => i + 1);
      setScreen("playing");
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
    const isBackward = data.mode === "backward";
    return (
      <div style={styles.container}>
        <h2>Digit Span Test ({isBackward ? "Backward" : "Forward"})</h2>
        <div style={styles.instructions}>
          <p>Ascolterai una sequenza di numeri.</p>
          {isBackward ? (
            <p>Dovrai ripeterli in <strong>ordine inverso</strong>.</p>
          ) : (
            <p>Dovrai ripeterli <strong>nello stesso ordine</strong>.</p>
          )}
          <p>Digita i numeri separati da spazi o tutti attaccati.</p>
          <p><em>In una versione completa, risponderesti a voce e il sistema trascriverebbe automaticamente.</em></p>
          <button style={styles.button} onClick={() => setScreen("playing")}>
            Inizia
          </button>
        </div>
      </div>
    );
  }

  if (screen === "playing") {
    return (
      <div style={styles.container}>
        <p style={{ fontSize: "1.2rem", color: "#888" }}>
          Ascolta attentamente...
        </p>
        <div style={styles.digit}>
          {currentDigit !== null ? currentDigit : "•"}
        </div>
        <div style={styles.progress}>
          Sequenza {currentIdx + 1} / {data.sequences.length}
        </div>
      </div>
    );
  }

  if (screen === "responding") {
    const isBackward = data.mode === "backward";
    return (
      <div style={styles.container}>
        <p style={{ fontSize: "1.3rem" }}>
          Scrivi i numeri {isBackward ? "in ordine inverso" : "nello stesso ordine"}:
        </p>
        <input
          type="text"
          style={styles.input}
          value={userInput}
          onChange={e => setUserInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") handleSubmitResponse(); }}
          autoFocus
          inputMode="numeric"
        />
        <button style={styles.button} onClick={handleSubmitResponse}>
          Conferma
        </button>
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
    fontFamily: "system-ui, sans-serif",
  },
  instructions: {
    maxWidth: "600px", textAlign: "center", fontSize: "1.1rem", lineHeight: 1.6,
  },
  digit: {
    fontSize: "16rem", fontWeight: "bold", fontFamily: "monospace",
    color: "#2e5c8a", height: "18rem",
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  input: {
    fontSize: "2.5rem", padding: "1rem 2rem", textAlign: "center",
    border: "2px solid #2e5c8a", borderRadius: "8px", margin: "2rem 0",
    fontFamily: "monospace", width: "400px",
  },
  button: {
    padding: "1rem 3rem", fontSize: "1.2rem",
    background: "#2e5c8a", color: "white", border: "none",
    borderRadius: "8px", cursor: "pointer",
  },
  progress: {
    position: "fixed", bottom: "1rem", right: "1rem",
    fontSize: "0.9rem", color: "#888",
  },
};
