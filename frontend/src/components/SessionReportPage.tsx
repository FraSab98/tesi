/**
 * SessionReportPage — carica il report di una sessione dal backend
 * e lo mostra usando il ReportDashboard esistente. Gestisce anche
 * l'export PDF.
 */

import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  downloadSessionReportPdf,
  getSessionReport,
  SessionReportData,
} from "../api/client";
import { ReportDashboard } from "./ReportDashboard";
import { Card, Button, Icon } from "./ui";
import { colors } from "../styles/theme";

export function SessionReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const nav = useNavigate();
  const [report, setReport] = useState<SessionReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await getSessionReport(sessionId);
        setReport(r);
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        setError(
          err.response?.data?.detail ||
            err.message ||
            "Errore caricamento report"
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionId]);

  const handleExportPdf = async () => {
    if (!report) return;
    try {
      const blob = await downloadSessionReportPdf(report);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${report.patient.code}_${report.session_id.substring(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } };
      if (err.response?.status === 501) {
        alert(
          "Generazione PDF non disponibile: il pacchetto 'reportlab' non è installato sul backend."
        );
      } else {
        alert("Errore durante la generazione del PDF.");
      }
    }
  };

  if (loading) {
    return (
      <Card>
        <div style={{ padding: "1rem", color: colors.muted }}>
          Caricamento report in corso…
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card title="Report non disponibile" accent>
        <p style={{ margin: "0 0 1rem 0", color: colors.body }}>{error}</p>
        <p style={{ color: colors.muted, fontSize: "0.9rem" }}>
          Il report può essere generato solo dopo che il paziente ha completato
          almeno un test e le risposte sono state raccolte.
        </p>
        <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
          <Button variant="secondary" onClick={() => nav("/sessions")}>
            Torna alle sessioni
          </Button>
          {sessionId && (
            <Link to={`/run/${sessionId}`}>
              <Button variant="ghost">Vai al link paziente →</Button>
            </Link>
          )}
        </div>
      </Card>
    );
  }

  if (!report) return null;

  return (
    <div>
      <div style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <Button variant="ghost" size="sm" onClick={() => nav(-1)}>
          ← Indietro
        </Button>
      </div>
      <ReportDashboard report={report} onExportPdf={handleExportPdf} />
    </div>
  );
}
