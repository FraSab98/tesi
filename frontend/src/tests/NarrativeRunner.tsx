/**
 * NarrativeRunner — somministra il Narrative Task (quinto test).
 *
 * Mostra una consegna (es. "Raccontami la tua giornata perfetta" o la
 * descrizione di un'immagine) e raccoglie la risposta del paziente come
 * testo oppure come audio (MediaRecorder). La risposta viene inviata a
 * /responses/batch, dove il backend la instrada nella pipeline multi-canale.
 *
 * Il testo e' la modalita' piu' robusta (non richiede microfono ne' Whisper);
 * l'audio e' opzionale e adatto quando si vuole sfruttare anche la prosodia.
 */

import { useState, useRef, useEffect } from "react";
import { ResponseItem, submitResponsesBatch } from "../api/client";

interface NarrativeData {
  prompt_type: string;
  prompt_text: string;
  response_mode: string;       // "vocal" | "text" | "both"
  min_response_seconds: number;
  min_words: number;
  image_ref?: string | null;
  instructions?: string;
}

interface Props {
  sessionId: string;
  testConfigId: string;
  stimulusId: string;
  data: NarrativeData;
  onComplete: () => void;
}

export function NarrativeRunner({
  sessionId, testConfigId, stimulusId, data, onComplete,
}: Props) {
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [audioBase64, setAudioBase64] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(Date.now());

  useEffect(() => { startTimeRef.current = Date.now(); }, []);

  const allowAudio = data.response_mode === "vocal" || data.response_mode === "both";
  const allowText = data.response_mode === "text" || data.response_mode === "both";

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const canSubmit =
    !submitting && (audioBase64 !== null || (allowText && wordCount >= data.min_words));

  // ---- Registrazione audio ----
  const startRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const b64 = await blobToBase64(blob);
        setAudioBase64(b64);
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setRecording(true);
    } catch {
      setError("Microfono non disponibile. Puoi rispondere via testo.");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  // ---- Invio ----
  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);

    const rt = Date.now() - startTimeRef.current;
    const response: ResponseItem = {
      stimulus_id: stimulusId,
      session_id: sessionId,
      trial_index: 0,
      response_type: audioBase64 ? "vocal" : "key",
      response_value: audioBase64 ? null : text.trim(),
      reaction_time_ms: rt,
      ...(audioBase64 ? { audio_base64: audioBase64 } : {}),
    };

    try {
      await submitResponsesBatch({
        session_id: sessionId,
        test_config_id: testConfigId,
        responses: [response],
      });
      onComplete();
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || "Errore durante l'invio della risposta");
      setSubmitting(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Racconto</h2>

      {data.image_ref && (
        <img src={data.image_ref} alt="Immagine da descrivere" style={styles.image} />
      )}

      <p style={styles.prompt}>{data.prompt_text}</p>
      {data.instructions && <p style={styles.instructions}>{data.instructions}</p>}

      {allowText && (
        <>
          <textarea
            style={styles.textarea}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Scrivi qui la tua risposta..."
            disabled={submitting || audioBase64 !== null}
            rows={8}
          />
          <div style={styles.wordCount}>
            {wordCount} parole {wordCount < data.min_words && `(minimo consigliato: ${data.min_words})`}
          </div>
        </>
      )}

      {allowAudio && (
        <div style={styles.audioRow}>
          {!recording ? (
            <button style={styles.recordBtn} onClick={startRecording} disabled={submitting}>
              {audioBase64 ? "🎙️ Registra di nuovo" : "🎙️ Registra risposta"}
            </button>
          ) : (
            <button style={styles.stopBtn} onClick={stopRecording}>
              ⏹️ Ferma registrazione
            </button>
          )}
          {audioBase64 && !recording && <span style={styles.audioOk}>✓ Audio registrato</span>}
        </div>
      )}

      {error && <div style={styles.error}>{error}</div>}

      <button style={styles.submitBtn} onClick={handleSubmit} disabled={!canSubmit}>
        {submitting ? "Invio..." : "Invia e continua"}
      </button>
    </div>
  );
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1]); // rimuove il prefisso data:...;base64,
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 640, margin: "2rem auto", padding: "2rem", fontFamily: "system-ui, sans-serif" },
  heading: { fontSize: "1.4rem", marginBottom: "1rem" },
  image: { maxWidth: "100%", borderRadius: 8, marginBottom: "1rem" },
  prompt: { fontSize: "1.25rem", fontWeight: 600, lineHeight: 1.5, marginBottom: "0.5rem" },
  instructions: { color: "#555", marginBottom: "1.5rem" },
  textarea: { width: "100%", fontSize: "1rem", padding: "0.75rem", borderRadius: 8, border: "1px solid #ccc", fontFamily: "inherit", resize: "vertical" },
  wordCount: { fontSize: "0.85rem", color: "#777", marginTop: "0.25rem" },
  audioRow: { display: "flex", alignItems: "center", gap: "1rem", marginTop: "1rem" },
  recordBtn: { padding: "0.6rem 1.2rem", borderRadius: 8, border: "1px solid #1976D2", background: "white", color: "#1976D2", cursor: "pointer", fontSize: "1rem" },
  stopBtn: { padding: "0.6rem 1.2rem", borderRadius: 8, border: "none", background: "#C62828", color: "white", cursor: "pointer", fontSize: "1rem" },
  audioOk: { color: "#43A047", fontWeight: 600 },
  error: { marginTop: "1rem", padding: "0.75rem", background: "#f8d7da", color: "#721c24", borderRadius: 8 },
  submitBtn: { marginTop: "1.5rem", width: "100%", padding: "0.9rem", borderRadius: 8, border: "none", background: "#1976D2", color: "white", fontSize: "1.05rem", cursor: "pointer", opacity: 1 },
};
