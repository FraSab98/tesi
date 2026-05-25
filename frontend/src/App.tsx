/**
 * App — router principale.
 *
 * Tutte le pagine del medico sono dentro <Layout> (sidebar + topbar).
 * La route /run/:sessionId per il paziente è fuori dal layout:
 * il paziente non deve vedere l'UI del medico.
 */

import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import { Layout } from "./components/Layout";
import { HomePage } from "./components/HomePage";
import { PatientsPage } from "./components/PatientsPage";
import { SessionsPage } from "./components/SessionsPage";
import { NewSessionPage } from "./components/NewSessionPage";
import { SessionReportPage } from "./components/SessionReportPage";
import { MultichannelPage } from "./components/MultichannelPage";
import { LongitudinalPage } from "./components/LongitudinalPage";
import { SessionRunner } from "./components/SessionRunner";
import { AnalysisHistory } from "./components/AnalysisHistory";

function RunWrapper() {
  const { sessionId } = useParams<{ sessionId: string }>();
  if (!sessionId) return <Navigate to="/" />;
  return <SessionRunner sessionId={sessionId} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
	<Route path="/analyses" element={<AnalysisHistory />} />
        {/* Area medico */}
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/patients" element={<PatientsPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/sessions/new" element={<NewSessionPage />} />
          <Route path="/sessions/:sessionId/report" element={<SessionReportPage />} />
          <Route path="/analyze" element={<MultichannelPage />} />
          <Route path="/longitudinal" element={<LongitudinalPage />} />
        </Route>

        {/* Area paziente (senza sidebar) */}
        <Route path="/run/:sessionId" element={<RunWrapper />} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
