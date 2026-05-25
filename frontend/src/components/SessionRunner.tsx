/**
 * SessionRunner — gestisce l'esecuzione di una sessione completa.
 *
 * Carica gli stimoli dal backend e instrada ogni test al Runner corretto,
 * in ordine di priorità. Al termine di ogni test passa al successivo.
 */

import { useState, useEffect } from "react";
import { getSessionStimuli } from "../api/client";
import { CPTRunner } from "../tests/CPTRunner";
import { DigitSpanRunner } from "../tests/DigitSpanRunner";
import { StroopRunner } from "../tests/StroopRunner";
import { GoNoGoRunner } from "../tests/GoNoGoRunner";
import { NarrativeRunner } from "../tests/NarrativeRunner";

interface TestConfig {
  test_config_id: string;
  test_type: string;
  order: number;
  config: Record<string, unknown>;
  stimuli: Array<{
    id: string;
    data: Record<string, unknown>;
    llm_provider: string;
  }>;
}

interface Props {
  sessionId: string;
}

export function SessionRunner({ sessionId }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tests, setTests] = useState<TestConfig[]>([]);
  const [currentTestIdx, setCurrentTestIdx] = useState(0);
  const [sessionComplete, setSessionComplete] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await getSessionStimuli(sessionId);
        setTests(data.sort((a: TestConfig, b: TestConfig) => a.order - b.order));
      } catch (e: unknown) {
        const err = e as { message?: string };
        setError(err.message || "Errore caricamento");
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionId]);

  const handleTestComplete = () => {
    if (currentTestIdx < tests.length - 1) {
      setCurrentTestIdx(i => i + 1);
    } else {
      setSessionComplete(true);
    }
  };

  if (loading) return <div style={styles.message}>Caricamento sessione...</div>;
  if (error) return <div style={styles.error}>Errore: {error}</div>;
  if (tests.length === 0) return <div style={styles.message}>Nessun test nella sessione.</div>;

  if (sessionComplete) {
    return (
      <div style={styles.completeBox}>
        <h2>🎉 Sessione completata</h2>
        <p>Grazie per la partecipazione!</p>
        <p>I risultati sono stati inviati al medico.</p>
      </div>
    );
  }

  const currentTest = tests[currentTestIdx];
  const currentStim = currentTest.stimuli[0];

  if (!currentStim) {
    return <div style={styles.error}>Stimoli non disponibili per {currentTest.test_type}</div>;
  }

  const commonProps = {
    sessionId,
    testConfigId: currentTest.test_config_id,
    stimulusId: currentStim.id,
    onComplete: handleTestComplete,
  };

  // Progress bar
  const progressBar = (
    <div style={styles.progressBar}>
      <div style={{
        ...styles.progressFill,
        width: `${(currentTestIdx / tests.length) * 100}%`,
      }} />
      <span style={styles.progressText}>
        Test {currentTestIdx + 1} di {tests.length}: {currentTest.test_type}
      </span>
    </div>
  );

  return (
    <div>
      {progressBar}
      {currentTest.test_type === "CPT" && (
        // @ts-expect-error: tipizzazione dinamica stimoli
        <CPTRunner {...commonProps} data={currentStim.data} />
      )}
      {currentTest.test_type === "DigitSpan" && (
        // @ts-expect-error
        <DigitSpanRunner {...commonProps} data={currentStim.data} />
      )}
      {currentTest.test_type === "Stroop" && (
        // @ts-expect-error
        <StroopRunner {...commonProps} data={currentStim.data} />
      )}
      {currentTest.test_type === "GoNoGo" && (
        // @ts-expect-error
        <GoNoGoRunner {...commonProps} data={currentStim.data} />
      )}
      {currentTest.test_type === "Narrative" && (
        // @ts-expect-error
        <NarrativeRunner {...commonProps} data={currentStim.data} />
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  message: {
    textAlign: "center", padding: "4rem", fontSize: "1.2rem",
    fontFamily: "system-ui, sans-serif",
  },
  error: {
    padding: "2rem", background: "#f8d7da", color: "#721c24",
    borderRadius: "8px", margin: "2rem",
  },
  completeBox: {
    textAlign: "center", padding: "4rem", fontFamily: "system-ui, sans-serif",
  },
  progressBar: {
    position: "fixed", top: 0, left: 0, right: 0, height: "6px",
    background: "#e9ecef", zIndex: 100,
  },
  progressFill: {
    height: "100%", background: "#2e5c8a", transition: "width 0.5s",
  },
  progressText: {
    position: "absolute", top: "10px", right: "1rem",
    fontSize: "0.85rem", color: "#6c757d",
  },
};
