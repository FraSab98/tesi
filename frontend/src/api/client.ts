/**
 * Wrapper axios per chiamate al backend.
 */

import axios, { AxiosInstance } from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// ============ PATIENTS ============

export interface Patient {
  id: string;
  external_code: string;
  age: number;
  language: string;
  education_years?: number;
  clinical_suspicion?: string | null;
  sensory_deficits?: Record<string, unknown>;
  handedness: string;
  created_at: string;
}

export async function createPatient(data: Partial<Patient>): Promise<Patient> {
  const resp = await api.post<Patient>("/patients", data);
  return resp.data;
}

export async function listPatients(): Promise<Patient[]> {
  const resp = await api.get<Patient[]>("/patients");
  return resp.data;
}

export async function getPatient(id: string): Promise<Patient> {
  const resp = await api.get<Patient>(`/patients/${id}`);
  return resp.data;
}

export async function getPatientReports(id: string): Promise<SessionReportData[]> {
  const resp = await api.get<SessionReportData[]>(`/patients/${id}/reports`);
  return resp.data;
}

// ============ SESSIONS ============

export interface TestConfigInput {
  test_type: "CPT" | "DigitSpan" | "Stroop" | "GoNoGo";
  order: number;
  config: Record<string, unknown>;
}

export interface SessionBuildInput {
  patient_id: string;
  clinician_id: string;
  tests: TestConfigInput[];
  notes?: string;
}

export interface SessionResponse {
  id: string;
  patient_id: string;
  clinician_id: string;
  status: string;
  session_token: string;
  notes?: string;
  created_at?: string;
  completed_at?: string | null;
  test_configs: Array<{
    id: string;
    test_type: string;
    order: number;
    config: Record<string, unknown>;
    stimulus_count?: number;
  }>;
}

export interface SessionListItem {
  id: string;
  patient_id: string;
  patient_code: string;
  patient_age: number;
  clinician_id: string;
  status: string;
  session_token: string;
  notes?: string | null;
  created_at: string;
  completed_at: string | null;
  n_tests: number;
  n_scored: number;
  test_types: string[];
}

export async function buildSession(data: SessionBuildInput): Promise<SessionResponse> {
  const resp = await api.post<SessionResponse>("/sessions/build", data);
  return resp.data;
}

export async function listSessions(params?: {
  patient_id?: string;
  status_filter?: string;
}): Promise<SessionListItem[]> {
  const resp = await api.get<SessionListItem[]>("/sessions", { params });
  return resp.data;
}

export async function getSession(id: string): Promise<SessionResponse> {
  const resp = await api.get<SessionResponse>(`/sessions/${id}`);
  return resp.data;
}

export async function getSessionStimuli(sessionId: string) {
  const resp = await api.get(`/sessions/${sessionId}/stimuli`);
  return resp.data;
}

// ============ RESPONSES ============

export interface ResponseItem {
  stimulus_id: string;
  session_id: string;
  trial_index: number;
  response_type: "click" | "key" | "vocal" | "none";
  response_value?: string | null;
  reaction_time_ms?: number | null;
  audio_base64?: string;
}

export interface ResponseBatchInput {
  session_id: string;
  test_config_id: string;
  responses: ResponseItem[];
}

export async function submitResponsesBatch(data: ResponseBatchInput) {
  const resp = await api.post("/responses/batch", data);
  return resp.data;
}

export async function getSessionScores(sessionId: string) {
  const resp = await api.get(`/responses/scores/${sessionId}`);
  return resp.data;
}

// ============ REPORTS ============

export interface SessionReportData {
  session_id: string;
  session_date: string;
  clinician_id: string;
  patient: {
    code: string;
    age: number;
    language: string;
    clinical_suspicion?: string | null;
  };
  test_scores: Array<{
    test_type: string;
    scores: Record<string, unknown>;
    flags: string[];
    clinical_note: string;
  }>;
  multichannel?: {
    avg_cognitive_strain: number;
    avg_emotional_distress: number;
    avg_communication_quality: number;
    n_audio_responses: number;
    dominant_emotions: Record<string, number>;
  } | null;
  overall_cognitive_score: number;
  overall_risk_level: "low" | "medium" | "high";
  key_findings: string[];
  recommendations: string[];
}

export async function getSessionReport(sessionId: string): Promise<SessionReportData> {
  const resp = await api.get<SessionReportData>(`/sessions/${sessionId}/report`);
  return resp.data;
}

export async function downloadSessionReportPdf(report: SessionReportData): Promise<Blob> {
  const resp = await api.post("/reports/session/pdf", report, {
    responseType: "blob",
  });
  return resp.data;
}

export async function analyzeLongitudinal(reports: SessionReportData[]) {
  const resp = await api.post("/reports/longitudinal", { reports });
  return resp.data;
}

// ============ ANALYSIS (multi-canale) ============

export async function analyzeText(data: {
  text: string;
  language?: string;
  session_id?: string;
  response_id?: string;
}) {
  const resp = await api.post("/analyze/text", { language: "it", ...data });
  return resp.data;
}

export async function analyzeAudio(data: {
  audio_base64: string;
  audio_format: string;
  language?: string;
  session_id: string;
  response_id: string;
  initial_prompt?: string;
  async_mode?: boolean;
}) {
  const resp = await api.post("/analyze/audio", {
    language: "it",
    async_mode: false,
    ...data,
  });
  return resp.data;
}
