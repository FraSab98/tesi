/**
 * MultichannelPage — analisi multicanale "ad hoc":
 * l'utente incolla testo o carica un file audio e vede
 * la scomposizione in: linguistic / prosodic / sentiment / emotion.
 *
 * Non richiede una sessione: utile per demo, test clinici veloci,
 * o verifiche post-hoc su un audio raccolto esternamente.
 */

import React, { useEffect, useRef, useState } from "react";
import { analyzeAudio, analyzeText } from "../api/client";
import { Card, Button, Badge, Icon } from "./ui";
import { colors, font, radius } from "../styles/theme";

type Tab = "text" | "audio";

export function MultichannelPage() {
  const [tab, setTab] = useState<Tab>("text");

  return (
    <div>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ marginBottom: "0.25rem" }}>Analisi multicanale</h1>
        <p style={{ margin: 0, color: colors.muted, maxWidth: 720 }}>
          Decomposizione di una risposta verbale in quattro canali: linguistico (fluenza,
          sintassi), prosodico (tempo, pause, energia), sentiment e emozioni discrete.
          Qui in modalità singola, fuori da una sessione.
        </p>
      </header>

      <div style={{ display: "flex", gap: "0.25rem", marginBottom: "1rem" }}>
        <TabBtn active={tab === "text"} onClick={() => setTab("text")}>
          Testo
        </TabBtn>
        <TabBtn active={tab === "audio"} onClick={() => setTab("audio")}>
          Audio
        </TabBtn>
      </div>

      {tab === "text" ? <TextAnalysisPanel /> : <AudioAnalysisPanel />}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "0.4rem 0.9rem",
        background: active ? colors.ink2 : "transparent",
        color: active ? "#fff" : colors.body,
        border: `1px solid ${active ? colors.ink2 : colors.border}`,
        borderRadius: radius.pill,
        cursor: "pointer",
        fontSize: "0.88rem",
        fontWeight: 500,
      }}
    >
      {children}
    </button>
  );
}

// ============ TEXT ============

function TextAnalysisPanel() {
  const [text, setText] = useState(
    "Ieri sono andato al mercato a comprare la frutta, poi… ehm… volevo andare in farmacia ma mi sono dimenticato dove fosse."
  );
  const [language, setLanguage] = useState("it");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await analyzeText({ text, language });
      setResult(r);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || "Errore durante l'analisi");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Card title="Input testuale" accent>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          <textarea
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{
              width: "100%",
              padding: "0.75rem",
              border: `1px solid ${colors.border}`,
              borderRadius: radius.md,
              fontSize: "0.95rem",
              fontFamily: "inherit",
              resize: "vertical",
              lineHeight: 1.5,
            }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
            <label style={{ fontSize: "0.88rem", color: colors.muted }}>
              Lingua:{" "}
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                style={{ padding: "0.2rem 0.5rem", border: `1px solid ${colors.border}`, borderRadius: 4 }}
              >
                <option value="it">Italiano</option>
                <option value="en">English</option>
              </select>
            </label>
            <Button onClick={run} disabled={loading || !text.trim()}>
              {loading ? "Analisi in corso…" : "Analizza"}
            </Button>
          </div>
        </div>
      </Card>

      {error && (
        <div style={errorBox}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <AnalysisResultView result={result} />
        </div>
      )}
    </>
  );
}

// ============ AUDIO ============

function AudioAnalysisPanel() {
  const [inputMode, setInputMode] = useState<"record" | "upload">("record");
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileBase64, setFileBase64] = useState<string | null>(null);
  const [fileFormat, setFileFormat] = useState<string>("webm");
  const [language, setLanguage] = useState("it");
  const [initialPrompt, setInitialPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const setAudioSource = (base64: string, format: string, name: string) => {
    if (!base64) {
      // reset
      setFileBase64(null);
      setFileName(null);
      setFileFormat("webm");
    } else {
      setFileBase64(base64);
      setFileName(name);
      setFileFormat(format);
    }
    setResult(null);
    setError(null);
  };

  const onPick = async (f: File) => {
    const ext = (f.name.split(".").pop() || "wav").toLowerCase();
    const allowed = ["wav", "mp3", "m4a", "webm", "ogg"];
    const format = allowed.includes(ext) ? ext : "wav";
    const buf = await f.arrayBuffer();
    const base64 = arrayBufferToBase64(buf);
    setAudioSource(base64, format, f.name);
  };

  const run = async () => {
    if (!fileBase64) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await analyzeAudio({
        audio_base64: fileBase64,
        audio_format: fileFormat,
        language,
        session_id: "adhoc",
        response_id: `adhoc_${Date.now()}`,
        initial_prompt: initialPrompt || undefined,
        async_mode: false,
      });
      setResult(resp as Record<string, unknown>);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || "Errore durante l'analisi audio");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Card title="Input audio" subtitle="Registra dal microfono oppure carica un file" accent>
        <div style={{ display: "grid", gap: "1rem" }}>
          {/* Switch modalità */}
          <div style={{ display: "flex", gap: "0.25rem" }}>
            <ModeTab active={inputMode === "record"} onClick={() => { setInputMode("record"); setAudioSource("", "", ""); }}>
              <Icon name="mic" size={14} /> Registra ora
            </ModeTab>
            <ModeTab active={inputMode === "upload"} onClick={() => { setInputMode("upload"); setAudioSource("", "", ""); }}>
              <Icon name="download" size={14} style={{ transform: "rotate(180deg)" }} /> Carica file
            </ModeTab>
          </div>

          {inputMode === "record" && (
            <RecordingInput onRecorded={setAudioSource} />
          )}

          {inputMode === "upload" && (
            <div
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const f = e.dataTransfer.files[0];
                if (f) onPick(f);
              }}
              style={{
                padding: "1.5rem",
                border: `2px dashed ${colors.border}`,
                borderRadius: radius.md,
                textAlign: "center",
                cursor: "pointer",
                background: colors.surface2,
              }}
            >
              <Icon name="mic" size={28} style={{ color: colors.ink2 }} />
              <div style={{ marginTop: "0.5rem", fontWeight: 500, color: colors.ink }}>
                {fileName ? fileName : "Clicca o trascina qui un file audio"}
              </div>
              <div style={{ fontSize: "0.85rem", color: colors.muted, marginTop: "0.3rem" }}>
                {fileName ? `Formato: ${fileFormat.toUpperCase()}` : "WAV, MP3, M4A, WebM, OGG — max ~25 MB"}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept="audio/*"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onPick(f);
                }}
              />
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "0.75rem" }}>
            <div>
              <Label>Lingua</Label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                style={inputStyle}
              >
                <option value="it">Italiano</option>
                <option value="en">English</option>
              </select>
            </div>
            <div>
              <Label>Prompt iniziale (contesto per la trascrizione)</Label>
              <input
                type="text"
                placeholder="es. 'cifre da 1 a 9' per Digit Span"
                value={initialPrompt}
                onChange={(e) => setInitialPrompt(e.target.value)}
                style={inputStyle}
              />
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Button onClick={run} disabled={loading || !fileBase64}>
              {loading ? "Analisi in corso… (può richiedere 30-90 secondi)" : "Analizza audio"}
            </Button>
          </div>
        </div>
      </Card>

      {error && <div style={errorBox}>{error}</div>}

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <AnalysisResultView result={result} />
        </div>
      )}
    </>
  );
}

// ============ RECORDING ============

function RecordingInput({
  onRecorded,
}: {
  onRecorded: (base64: string, format: string, name: string) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const finalElapsedRef = useRef(0);

  const cleanup = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async () => {
    setError(null);
    // Se c'era una preview precedente, pulisci
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    onRecorded("", "", "");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Scegli un MIME type supportato (webm su Chrome/Edge, mp4 su Safari)
      let mimeType = "audio/webm";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        if (MediaRecorder.isTypeSupported("audio/ogg")) mimeType = "audio/ogg";
        else if (MediaRecorder.isTypeSupported("audio/mp4")) mimeType = "audio/mp4";
        else mimeType = ""; // lascia decidere al browser
      }

      const mr = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      chunksRef.current = [];

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = async () => {
        const actualType = mr.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: actualType });

        // Mappa il mime type al formato che accetta il backend
        let format = "webm";
        if (actualType.includes("ogg")) format = "ogg";
        else if (actualType.includes("mp4") || actualType.includes("m4a")) format = "m4a";
        else if (actualType.includes("wav")) format = "wav";
        else if (actualType.includes("mpeg") || actualType.includes("mp3")) format = "mp3";

        // Encoding base64
        const buf = await blob.arrayBuffer();
        const base64 = arrayBufferToBase64(buf);

        // Preview
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);

        const ts = new Date().toISOString().substring(0, 19).replace(/[:\-T]/g, "");
        const name = `registrazione_${ts}.${format}`;
        onRecorded(base64, format, name);

        cleanup();
      };

      mr.start();
      setRecording(true);
      setElapsed(0);
      finalElapsedRef.current = 0;
      const startedAt = Date.now();
      timerRef.current = window.setInterval(() => {
        const e = Math.floor((Date.now() - startedAt) / 1000);
        setElapsed(e);
        finalElapsedRef.current = e;
      }, 250);
    } catch (e: unknown) {
      const err = e as { name?: string; message?: string };
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setError(
          "Permesso microfono negato. Abilita l'accesso nelle impostazioni del browser e ricarica la pagina."
        );
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        setError("Nessun microfono trovato sul dispositivo.");
      } else {
        setError(err.message || "Errore durante l'avvio della registrazione");
      }
      cleanup();
    }
  };

  const stop = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  const discard = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setElapsed(0);
    finalElapsedRef.current = 0;
    onRecorded("", "", "");
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div>
      {error && <div style={{ ...errorBox, marginTop: 0, marginBottom: "0.75rem" }}>{error}</div>}

      {/* Stato: pronti a registrare */}
      {!recording && !previewUrl && (
        <div style={recBox}>
          <div style={recIcon}>
            <Icon name="mic" size={36} />
          </div>
          <p style={{ margin: "0 0 1rem 0", color: colors.muted, textAlign: "center" }}>
            Premi il pulsante e parla direttamente al microfono.
            <br />
            <span style={{ fontSize: "0.82rem" }}>
              Il browser ti chiederà il permesso la prima volta.
            </span>
          </p>
          <Button onClick={start}>
            <Icon name="mic" size={16} /> Avvia registrazione
          </Button>
        </div>
      )}

      {/* Stato: registrazione in corso */}
      {recording && (
        <div style={recBox}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <span style={pulseDot} />
            <span style={{ fontFamily: font.mono, fontSize: "2rem", color: colors.ink, fontWeight: 500 }}>
              {formatTime(elapsed)}
            </span>
          </div>
          <p style={{ margin: "0 0 1rem 0", color: colors.muted }}>
            Registrazione in corso… parla chiaramente.
          </p>
          <Button variant="danger" onClick={stop}>
            Ferma registrazione
          </Button>
        </div>
      )}

      {/* Stato: registrazione completata con preview */}
      {!recording && previewUrl && (
        <div style={{ ...recBox, alignItems: "stretch" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#065F46", fontWeight: 500, marginBottom: "0.75rem" }}>
            <Icon name="check" size={18} strokeWidth={2.5} />
            <span>Registrazione completata ({formatTime(finalElapsedRef.current)})</span>
          </div>
          <audio
            src={previewUrl}
            controls
            style={{ width: "100%", marginBottom: "1rem" }}
          />
          <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center" }}>
            <Button variant="ghost" onClick={discard}>
              Scarta
            </Button>
            <Button variant="secondary" onClick={start}>
              <Icon name="mic" size={14} /> Registra di nuovo
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper piccolo ma usato in più punti
function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function ModeTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
        padding: "0.35rem 0.85rem",
        border: `1px solid ${active ? colors.ink2 : colors.border}`,
        borderRadius: radius.pill,
        background: active ? colors.ink2 : "transparent",
        color: active ? "#fff" : colors.body,
        fontSize: "0.85rem",
        fontWeight: 500,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

// ============ RESULT VIEW ============

/**
 * Mappa ogni metrica tecnica a un'interpretazione leggibile per il clinico.
 * Le soglie sono ORIENTATIVE, basate su intervalli tipici nella letteratura
 * (Barrios 2025 per linguistica narrativa; Cannizzaro 2004 per prosodia in MDD).
 * NON sostituiscono normative cliniche standardizzate.
 */

type Level = "ok" | "warn" | "risk";
type Interp = { level: Level; text: string };

const fmt = (v: unknown, decimals = 2): string => {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(decimals);
  return String(v);
};

function levelToTone(l: Level): "accent" | "warn" | "risk" {
  return l === "ok" ? "accent" : l === "warn" ? "warn" : "risk";
}

function levelColor(l: Level): string {
  return l === "ok" ? colors.accent : l === "warn" ? colors.warn : colors.risk;
}

function AnalysisResultView({ result }: { result: Record<string, unknown> }) {
  const r = (result.result || result) as Record<string, unknown>;

  const transcript = (r.transcript || r.text) as string | undefined;
  const linguistic = r.linguistic as Record<string, unknown> | undefined;
  const prosodic = r.prosodic as Record<string, unknown> | undefined;
  const sentiment = r.sentiment as Record<string, unknown> | undefined;
  const emotion = r.emotion as Record<string, unknown> | undefined;
  const channels = r.channels_available as string[] | undefined;

  // Indicatori compositi: top-level nel backend
  const cognitiveStrain = Number(r.cognitive_strain_index) || 0;
  const emotionalDistress = Number(r.emotional_distress_index) || 0;
  const communicationQuality = Number(r.communication_quality_index) || 0;

  const duration = prosodic ? Number(prosodic.duration_s) : null;

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {/* ====== SINTESI CLINICA ====== */}
      <Card title="Sintesi clinica" accent>
        <CompositeIndicators
          strain={cognitiveStrain}
          distress={emotionalDistress}
          quality={communicationQuality}
        />
        <ClinicalNarrative
          linguistic={linguistic}
          prosodic={prosodic}
          sentiment={sentiment}
          emotion={emotion}
          strain={cognitiveStrain}
          distress={emotionalDistress}
          quality={communicationQuality}
        />
      </Card>

      {/* ====== Meta ====== */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {channels?.map((c) => (
          <Badge key={c} tone="sky">
            canale: {translateChannel(c)}
          </Badge>
        ))}
        {duration != null && <Badge>durata: {duration.toFixed(1)}s</Badge>}
      </div>

      {/* ====== Trascrizione ====== */}
      {transcript && (
        <Card title="Trascrizione">
          <p style={{ margin: 0, lineHeight: 1.6, color: colors.ink, fontSize: "0.95rem" }}>
            {transcript}
          </p>
        </Card>
      )}

      {/* ====== Profilo linguistico ====== */}
      {linguistic && <LinguisticProfile data={linguistic} />}

      {/* ====== Profilo vocale ====== */}
      {prosodic && <ProsodicProfile data={prosodic} />}

      {/* ====== Stato emotivo ====== */}
      {(sentiment || emotion) && <EmotionProfile sentiment={sentiment} emotion={emotion} />}

      {/* ====== Nota + dettagli tecnici ====== */}
      <div
        style={{
          fontSize: "0.8rem",
          color: colors.muted,
          padding: "0.75rem 1rem",
          background: colors.surface3,
          borderRadius: radius.md,
          border: `1px solid ${colors.border}`,
          lineHeight: 1.5,
        }}
      >
        <strong style={{ color: colors.ink }}>Nota:</strong> le interpretazioni sono
        orientative e basate su intervalli tipici riportati in letteratura
        (non su normative cliniche standardizzate per popolazione italiana).
        Vanno integrate con valutazione clinica e contesto del paziente.
      </div>

      <details
        style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          padding: "0.5rem 1rem",
        }}
      >
        <summary style={{ cursor: "pointer", color: colors.muted, fontSize: "0.85rem", padding: "0.3rem 0" }}>
          Dati tecnici grezzi (JSON)
        </summary>
        <pre
          style={{
            margin: "0.5rem 0 0 0",
            padding: "0.75rem",
            background: colors.surface2,
            borderRadius: radius.sm,
            fontSize: "0.76rem",
            fontFamily: font.mono,
            overflow: "auto",
            maxHeight: 320,
            color: colors.body,
          }}
        >
          {JSON.stringify(result, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function translateChannel(c: string): string {
  const map: Record<string, string> = {
    linguistic: "linguaggio",
    prosodic: "prosodia",
    sentiment: "sentiment",
    emotion: "emozioni",
    transcript: "trascrizione",
  };
  return map[c] || c;
}

// ============ INDICATORI COMPOSITI ============

function CompositeIndicators({
  strain,
  distress,
  quality,
}: {
  strain: number;
  distress: number;
  quality: number;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
      <CompositeMetric
        label="Sforzo cognitivo"
        value={strain}
        inverse
        legendHigh="Elevato"
        legendLow="Minimo"
        explanation="Difficoltà complessiva del paziente nel produrre la risposta"
      />
      <CompositeMetric
        label="Disagio emotivo"
        value={distress}
        inverse
        legendHigh="Presente"
        legendLow="Assente"
        explanation="Livello di stress o tensione emotiva rilevato"
      />
      <CompositeMetric
        label="Qualità comunicazione"
        value={quality}
        legendHigh="Buona"
        legendLow="Compromessa"
        explanation="Chiarezza, fluenza e coerenza della produzione verbale"
      />
    </div>
  );
}

function CompositeMetric({
  label,
  value,
  inverse,
  legendHigh,
  legendLow,
  explanation,
}: {
  label: string;
  value: number;
  inverse?: boolean;
  legendHigh: string;
  legendLow: string;
  explanation: string;
}) {
  const v = Math.max(0, Math.min(100, value));
  const level: Level = inverse
    ? v > 66 ? "risk" : v > 33 ? "warn" : "ok"
    : v < 33 ? "risk" : v < 66 ? "warn" : "ok";
  const tone = levelColor(level);

  const verdict = inverse
    ? v > 66 ? legendHigh : v > 33 ? "Moderato" : legendLow
    : v > 66 ? legendHigh : v > 33 ? "Moderata" : legendLow;

  return (
    <div
      style={{
        padding: "1rem",
        background: colors.surface2,
        borderRadius: radius.md,
        border: `1px solid ${colors.border}`,
        borderLeft: `3px solid ${tone}`,
      }}
    >
      <div style={{ fontSize: "0.78rem", color: colors.muted, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 500 }}>
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.6rem", marginTop: "0.35rem" }}>
        <span style={{ fontFamily: font.display, fontSize: "1.9rem", fontWeight: 600, color: colors.ink, lineHeight: 1 }}>
          {v.toFixed(0)}
        </span>
        <span style={{ fontSize: "0.8rem", color: colors.muted }}>/ 100</span>
      </div>
      <div
        style={{
          display: "inline-block",
          marginTop: "0.5rem",
          padding: "0.15rem 0.5rem",
          background: level === "ok" ? colors.accentSoft : level === "warn" ? colors.warnSoft : colors.riskSoft,
          color: tone,
          borderRadius: radius.pill,
          fontSize: "0.78rem",
          fontWeight: 500,
        }}
      >
        {verdict}
      </div>
      <div
        style={{
          height: 3,
          background: colors.surface3,
          borderRadius: 3,
          marginTop: "0.6rem",
          overflow: "hidden",
        }}
      >
        <div style={{ width: `${v}%`, height: "100%", background: tone, transition: "width 400ms" }} />
      </div>
      <div style={{ fontSize: "0.78rem", color: colors.muted, marginTop: "0.5rem", lineHeight: 1.4 }}>
        {explanation}
      </div>
    </div>
  );
}

// ============ NARRATIVA CLINICA ============

function ClinicalNarrative({
  linguistic,
  prosodic,
  sentiment,
  emotion,
  strain,
  distress,
  quality,
}: {
  linguistic?: Record<string, unknown>;
  prosodic?: Record<string, unknown>;
  sentiment?: Record<string, unknown>;
  emotion?: Record<string, unknown>;
  strain: number;
  distress: number;
  quality: number;
}) {
  const sentences: string[] = [];

  // Frase apertura su produzione
  if (linguistic) {
    const wc = Number(linguistic.word_count) || 0;
    const sc = Number(linguistic.sentence_count) || 0;
    if (wc > 0) {
      sentences.push(
        `Il paziente ha prodotto ${wc} parole distribuite in ${sc} frasi (media ${fmt(linguistic.mean_sentence_length, 1)} parole per frase).`
      );
    }
  }

  // Ricchezza lessicale
  if (linguistic) {
    const mattr = Number(linguistic.mattr);
    if (!isNaN(mattr)) {
      if (mattr < 0.45)
        sentences.push("La varietà lessicale risulta ridotta, compatibile con un vocabolario ristretto o con difficoltà di recupero lessicale.");
      else if (mattr > 0.65)
        sentences.push("La varietà lessicale è elevata, indice di un vocabolario ampio e di buon recupero lessicale.");
      else
        sentences.push("La varietà lessicale è nella norma.");
    }
  }

  // Complessità sintattica
  if (linguistic) {
    const depth = Number(linguistic.mean_syntactic_depth);
    if (!isNaN(depth) && depth > 0) {
      if (depth < 2.5)
        sentences.push("La struttura sintattica è semplice, con poca subordinazione.");
      else if (depth > 4)
        sentences.push("La struttura sintattica è articolata, con uso significativo di subordinate.");
    }
  }

  // Prosodia: pitch
  if (prosodic) {
    const pitchStd = Number(prosodic.pitch_std_hz);
    if (!isNaN(pitchStd)) {
      if (pitchStd < 15)
        sentences.push("L'eloquio appare monotono, con variabilità tonale ridotta (possibile indicatore affettivo da integrare clinicamente).");
      else if (pitchStd > 45)
        sentences.push("L'eloquio mostra ampia variabilità tonale.");
    }
    const pauseRatio = Number(prosodic.pause_ratio);
    if (!isNaN(pauseRatio)) {
      if (pauseRatio > 0.35)
        sentences.push("Sono presenti frequenti pause (oltre un terzo del tempo), potenziale segno di difficoltà di recupero lessicale o pianificazione.");
    }
  }

  // Sentiment / emozione
  if (sentiment) {
    const label = String(sentiment.label || "").toLowerCase();
    if (label === "negative")
      sentences.push("Il contenuto verbale ha una tonalità emotiva prevalentemente negativa.");
    else if (label === "positive")
      sentences.push("Il contenuto verbale ha una tonalità emotiva prevalentemente positiva.");
  }
  if (emotion) {
    const dom = String(emotion.dominant || "");
    if (dom && dom !== "neutral") {
      sentences.push(`L'emozione dominante nel testo è ${translateEmotion(dom)}.`);
    }
  }

  // Chiusura con sintesi compositi
  if (strain > 66 || distress > 66 || quality < 34) {
    sentences.push("Nel complesso, più indicatori suggeriscono di approfondire la valutazione.");
  } else if (strain < 34 && distress < 34 && quality > 66) {
    sentences.push("Nel complesso, tutti gli indicatori compositi risultano favorevoli.");
  }

  if (sentences.length === 0) {
    return (
      <div style={{ color: colors.muted, fontSize: "0.9rem", fontStyle: "italic" }}>
        Dati insufficienti per una sintesi narrativa.
      </div>
    );
  }

  return (
    <div
      style={{
        fontSize: "0.95rem",
        lineHeight: 1.65,
        color: colors.body,
        padding: "0.9rem 1rem",
        background: colors.surface2,
        borderLeft: `3px solid ${colors.ink2}`,
        borderRadius: radius.sm,
      }}
    >
      {sentences.map((s, i) => (
        <span key={i}>
          {s}
          {i < sentences.length - 1 ? " " : ""}
        </span>
      ))}
    </div>
  );
}

function translateEmotion(e: string): string {
  const map: Record<string, string> = {
    joy: "gioia",
    happiness: "gioia",
    sadness: "tristezza",
    anger: "rabbia",
    fear: "paura",
    surprise: "sorpresa",
    disgust: "disgusto",
    love: "tenerezza",
    neutral: "neutra",
  };
  return map[e.toLowerCase()] || e;
}

// ============ PROFILO LINGUISTICO ============

function LinguisticProfile({ data }: { data: Record<string, unknown> }) {
  const wordCount = Number(data.word_count) || 0;
  const sentenceCount = Number(data.sentence_count) || 0;
  const meanLen = Number(data.mean_sentence_length) || 0;
  const mattr = Number(data.mattr) || 0;
  const density = Number(data.lexical_density) || 0;
  const cohesion = Number(data.cohesion) || 0;
  const depth = Number(data.mean_syntactic_depth) || 0;

  const mattrI: Interp =
    mattr < 0.45 ? { level: "risk", text: "Ridotta" }
    : mattr < 0.55 ? { level: "warn", text: "Al limite inferiore" }
    : mattr > 0.7 ? { level: "ok", text: "Elevata" }
    : { level: "ok", text: "Nella norma" };

  const densityI: Interp =
    density < 0.35 ? { level: "risk", text: "Bassa (eccesso parole funzionali)" }
    : density > 0.65 ? { level: "ok", text: "Alta (parlato informativo)" }
    : { level: "ok", text: "Nella norma" };

  const cohesionI: Interp =
    cohesion < 0.10 ? { level: "warn", text: "Ridotto uso di connettivi" }
    : cohesion > 0.25 ? { level: "warn", text: "Uso eccessivo di connettivi" }
    : { level: "ok", text: "Equilibrata" };

  const depthI: Interp =
    depth < 2.5 ? { level: "warn", text: "Sintassi semplice" }
    : depth > 4.5 ? { level: "ok", text: "Sintassi articolata" }
    : { level: "ok", text: "Nella norma" };

  const lenI: Interp =
    meanLen < 5 ? { level: "warn", text: "Frasi molto brevi" }
    : meanLen > 25 ? { level: "warn", text: "Frasi molto lunghe" }
    : { level: "ok", text: "Nella norma" };

  return (
    <Card title="Profilo linguistico" subtitle="Caratteristiche del linguaggio prodotto">
      <MetricGrid
        metrics={[
          {
            label: "Quantità prodotta",
            value: `${wordCount} parole · ${sentenceCount} frasi`,
            explanation: "Produzione verbale totale del paziente.",
          },
          {
            label: "Lunghezza media frase",
            value: `${meanLen.toFixed(1)} parole`,
            interp: lenI,
            explanation: "Frasi troppo brevi possono indicare difficoltà di elaborazione; troppo lunghe, scarsa pianificazione.",
          },
          {
            label: "Ricchezza lessicale (MATTR)",
            value: mattr.toFixed(2),
            interp: mattrI,
            explanation: "Varietà del vocabolario usato. Valori bassi possono suggerire deterioramento cognitivo o afasia.",
          },
          {
            label: "Densità semantica",
            value: `${(density * 100).toFixed(0)}%`,
            interp: densityI,
            explanation: "Proporzione di parole significative (nomi, verbi, aggettivi). Bassa densità può indicare circonlocuzione.",
          },
          {
            label: "Coesione",
            value: `${(cohesion * 100).toFixed(0)}%`,
            interp: cohesionI,
            explanation: "Uso di connettivi logici tra le frasi. Indica capacità di costruire un discorso coerente.",
          },
          {
            label: "Complessità sintattica",
            value: depth.toFixed(2),
            interp: depthI,
            explanation: "Profondità media dell'albero sintattico. Valori alti = frasi con più subordinate.",
          },
        ]}
      />
    </Card>
  );
}

// ============ PROFILO VOCALE (PROSODIA) ============

function ProsodicProfile({ data }: { data: Record<string, unknown> }) {
  const duration = Number(data.duration_s) || 0;
  const meanPitch = Number(data.mean_pitch_hz) || 0;
  const pitchStd = Number(data.pitch_std_hz) || 0;
  const pauseRatio = Number(data.pause_ratio) || 0;
  const nPauses = Number(data.n_pauses) || 0;
  const jitter = Number(data.jitter) || 0;
  const shimmer = Number(data.shimmer) || 0;

  const pitchStdI: Interp =
    pitchStd < 15 ? { level: "warn", text: "Eloquio monotono" }
    : pitchStd > 45 ? { level: "ok", text: "Molto variabile" }
    : { level: "ok", text: "Variabilità normale" };

  const pauseI: Interp =
    pauseRatio > 0.35 ? { level: "warn", text: "Pause frequenti" }
    : pauseRatio > 0.20 ? { level: "ok", text: "Pause moderate" }
    : { level: "ok", text: "Eloquio fluente" };

  const jitterI: Interp =
    jitter > 0.02 ? { level: "warn", text: "Elevato — instabilità vocale" }
    : { level: "ok", text: "Nella norma" };

  const shimmerI: Interp =
    shimmer > 0.06 ? { level: "warn", text: "Elevato — instabilità energia" }
    : { level: "ok", text: "Nella norma" };

  return (
    <Card title="Profilo vocale" subtitle="Caratteristiche acustiche e prosodiche">
      <MetricGrid
        metrics={[
          {
            label: "Durata totale",
            value: `${duration.toFixed(1)} secondi`,
            explanation: "Lunghezza dell'audio analizzato.",
          },
          {
            label: "Pitch medio",
            value: `${meanPitch.toFixed(0)} Hz`,
            explanation: "Frequenza fondamentale media della voce (dipende anche da età e sesso del paziente).",
          },
          {
            label: "Variabilità del pitch",
            value: `${pitchStd.toFixed(1)} Hz`,
            interp: pitchStdI,
            explanation: "Bassa variabilità (< 15 Hz) indica eloquio monotono, possibile indicatore depressivo o parkinsoniano.",
          },
          {
            label: "Pause",
            value: `${nPauses} pause · ${(pauseRatio * 100).toFixed(0)}% del tempo`,
            interp: pauseI,
            explanation: "Pause frequenti o lunghe possono riflettere difficoltà di recupero lessicale o pianificazione.",
          },
          {
            label: "Jitter",
            value: jitter.toFixed(4),
            interp: jitterI,
            explanation: "Variazione ciclo-per-ciclo della frequenza. Valori alti indicano instabilità delle corde vocali.",
          },
          {
            label: "Shimmer",
            value: shimmer.toFixed(4),
            interp: shimmerI,
            explanation: "Variazione dell'ampiezza. Valori alti possono indicare affaticamento o disfonia.",
          },
        ]}
      />
    </Card>
  );
}

// ============ PROFILO EMOTIVO ============

function EmotionProfile({
  sentiment,
  emotion,
}: {
  sentiment?: Record<string, unknown>;
  emotion?: Record<string, unknown>;
}) {
  const sentLabel = String(sentiment?.label || "");
  const sentScore = Number(sentiment?.score) || 0;
  const emotions = (emotion?.emotions as Record<string, number> | undefined) || {};
  const dominant = String(emotion?.dominant || "");
  const dominantScore = Number(emotion?.dominant_score) || 0;

  // Ordina le emozioni per score desc
  const sortedEmotions = Object.entries(emotions).sort(([, a], [, b]) => Number(b) - Number(a));

  return (
    <Card title="Stato emotivo" subtitle="Sentiment e emozioni rilevate nel contenuto verbale">
      <div style={{ display: "grid", gridTemplateColumns: sentiment && emotion ? "1fr 1fr" : "1fr", gap: "1.25rem" }}>
        {sentiment && (
          <div>
            <SubHeader>Tonalità generale</SubHeader>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.35rem" }}>
              <SentimentBadge label={sentLabel} />
              <span style={{ color: colors.muted, fontSize: "0.85rem" }}>
                confidenza {(sentScore * 100).toFixed(0)}%
              </span>
            </div>
            <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.88rem", color: colors.muted, lineHeight: 1.5 }}>
              {sentLabel === "negative"
                ? "Il contenuto verbale del paziente tende a esprimere stati o eventi negativi."
                : sentLabel === "positive"
                ? "Il contenuto verbale del paziente tende a esprimere stati o eventi positivi."
                : "Il contenuto è tonalmente neutro, senza forti polarizzazioni emotive."}
            </p>
          </div>
        )}

        {emotion && (
          <div>
            <SubHeader>Emozione dominante</SubHeader>
            <div style={{ marginBottom: "0.5rem" }}>
              <span
                style={{
                  display: "inline-block",
                  padding: "0.3rem 0.8rem",
                  background: colors.skySoft,
                  color: "#075985",
                  borderRadius: radius.pill,
                  fontWeight: 500,
                  fontSize: "0.9rem",
                  textTransform: "capitalize",
                }}
              >
                {translateEmotion(dominant)}
              </span>
              <span style={{ color: colors.muted, fontSize: "0.85rem", marginLeft: "0.5rem" }}>
                {(dominantScore * 100).toFixed(0)}%
              </span>
            </div>
            {sortedEmotions.length > 1 && (
              <div style={{ marginTop: "0.75rem" }}>
                <div style={{ fontSize: "0.78rem", color: colors.muted, marginBottom: "0.4rem" }}>
                  Distribuzione completa
                </div>
                {sortedEmotions.map(([emo, score]) => (
                  <div
                    key={emo}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "110px 1fr 45px",
                      alignItems: "center",
                      gap: "0.6rem",
                      marginBottom: "0.3rem",
                      fontSize: "0.85rem",
                    }}
                  >
                    <span style={{ color: colors.body, textTransform: "capitalize" }}>
                      {translateEmotion(emo)}
                    </span>
                    <div
                      style={{
                        height: 6,
                        background: colors.surface3,
                        borderRadius: 6,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${Math.min(100, Number(score) * 100)}%`,
                          height: "100%",
                          background: emo === dominant ? colors.ink2 : colors.soft,
                        }}
                      />
                    </div>
                    <span
                      style={{
                        textAlign: "right",
                        color: colors.muted,
                        fontFamily: font.mono,
                        fontSize: "0.78rem",
                      }}
                    >
                      {(Number(score) * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function SentimentBadge({ label }: { label: string }) {
  const cfg: Record<string, { bg: string; fg: string; text: string }> = {
    positive: { bg: colors.accentSoft, fg: "#065F46", text: "Positivo" },
    negative: { bg: colors.riskSoft, fg: "#991B1B", text: "Negativo" },
    neutral: { bg: colors.surface3, fg: colors.body, text: "Neutro" },
  };
  const c = cfg[label.toLowerCase()] || cfg.neutral;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "0.3rem 0.85rem",
        background: c.bg,
        color: c.fg,
        borderRadius: radius.pill,
        fontWeight: 500,
        fontSize: "0.9rem",
      }}
    >
      {c.text}
    </span>
  );
}

function SubHeader({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: "0.72rem",
        color: colors.muted,
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        fontWeight: 500,
        marginBottom: "0.5rem",
      }}
    >
      {children}
    </div>
  );
}

// ============ GRIGLIA GENERICA METRICHE ============

interface Metric {
  label: string;
  value: string;
  interp?: Interp;
  explanation: string;
}

function MetricGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
      {metrics.map((m, i) => (
        <div
          key={i}
          style={{
            padding: "0.85rem 1rem",
            background: colors.surface2,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            borderLeft: m.interp ? `3px solid ${levelColor(m.interp.level)}` : `3px solid ${colors.border}`,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: colors.muted, fontWeight: 500 }}>{m.label}</span>
            {m.interp && <Badge tone={levelToTone(m.interp.level)}>{m.interp.text}</Badge>}
          </div>
          <div style={{ fontFamily: font.display, fontSize: "1.1rem", fontWeight: 500, color: colors.ink }}>
            {m.value}
          </div>
          <div style={{ fontSize: "0.78rem", color: colors.muted, marginTop: "0.4rem", lineHeight: 1.4 }}>
            {m.explanation}
          </div>
        </div>
      ))}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
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
      {children}
    </span>
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

const errorBox: React.CSSProperties = {
  marginTop: "1rem",
  padding: "0.75rem 1rem",
  background: colors.riskSoft,
  color: colors.risk,
  borderRadius: radius.md,
  fontSize: "0.9rem",
};

const recBox: React.CSSProperties = {
  padding: "1.75rem 1.5rem",
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  background: colors.surface2,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  minHeight: 180,
};

const recIcon: React.CSSProperties = {
  width: 64,
  height: 64,
  borderRadius: "50%",
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  display: "grid",
  placeItems: "center",
  color: colors.ink2,
  marginBottom: "0.9rem",
};

const pulseDot: React.CSSProperties = {
  width: 14,
  height: 14,
  borderRadius: "50%",
  background: colors.risk,
  boxShadow: `0 0 0 0 ${colors.risk}`,
  animation: "recPulse 1.3s infinite",
  display: "inline-block",
};

// Iniezione una-tantum del keyframe per il pulse
if (typeof document !== "undefined" && !document.getElementById("rec-pulse-style")) {
  const s = document.createElement("style");
  s.id = "rec-pulse-style";
  s.textContent = `@keyframes recPulse {
    0%   { box-shadow: 0 0 0 0 rgba(185, 28, 28, 0.55); }
    70%  { box-shadow: 0 0 0 14px rgba(185, 28, 28, 0); }
    100% { box-shadow: 0 0 0 0 rgba(185, 28, 28, 0); }
  }`;
  document.head.appendChild(s);
}
