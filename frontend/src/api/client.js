/**
 * Axios client with automatic session-ID injection.
 *
 * Session ID lifecycle:
 *   - On first load, POST /api/session/new to create a session.
 *   - The UUID is persisted in localStorage under "nsrag_session_id".
 *   - Every request includes it as the X-Session-ID header.
 *   - Callers can call initSession() to ensure a session exists.
 */

import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "";

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,   // 2 min — story generation + benchmarks can be slow
  headers: { "Content-Type": "application/json" },
});

// Inject session ID on every request
api.interceptors.request.use((config) => {
  const sid = localStorage.getItem("nsrag_session_id");
  if (sid) config.headers["X-Session-ID"] = sid;
  return config;
});

// ── Session helpers ───────────────────────────────────────────────────────────

export async function initSession() {
  let sid = localStorage.getItem("nsrag_session_id");
  if (sid) {
    try {
      await api.get("/api/session/info");
      return sid;
    } catch {
      // Session expired or not found on server — create a new one
    }
  }
  const { data } = await api.post("/api/session/new");
  localStorage.setItem("nsrag_session_id", data.session_id);
  return data.session_id;
}

export function clearSession() {
  localStorage.removeItem("nsrag_session_id");
}

export async function resetSession() {
  await api.post("/api/session/reset");
}

// ── Story ────────────────────────────────────────────────────────────────────

export const generateStory = (user_input) =>
  api.post("/api/story/generate", { user_input }).then((r) => r.data);

export const getHistory = () =>
  api.get("/api/story/history").then((r) => r.data.history);

export const getViolations = () =>
  api.get("/api/story/violations").then((r) => r.data);

export const clearViolations = () =>
  api.delete("/api/story/violations").then((r) => r.data);

export const getRecentFacts = (n = 30) =>
  api.get(`/api/story/facts?n=${n}`).then((r) => r.data);

export const getWorldState = () =>
  api.get("/api/story/state").then((r) => r.data);

// ── Metrics ──────────────────────────────────────────────────────────────────

export const getMetrics = () =>
  api.get("/api/metrics").then((r) => r.data);

// ── Graph ────────────────────────────────────────────────────────────────────

export const getCurrentGraph = (mode = "state", top_n = 20, highlight = true) =>
  api
    .get(`/api/graph/current?mode=${mode}&top_n=${top_n}&highlight_violations=${highlight}`)
    .then((r) => r.data);

export const getHistoricalGraph = (top_n = 50) =>
  api.get(`/api/graph/historical?top_n=${top_n}`).then((r) => r.data);

export const getGraphStats = () =>
  api.get("/api/graph/stats").then((r) => r.data);

export const getEntityFacts = (name) =>
  api.get(`/api/graph/entity/${encodeURIComponent(name)}`).then((r) => r.data);

export const searchEntities = (q) =>
  api.get(`/api/graph/search?q=${encodeURIComponent(q)}`).then((r) => r.data);

// ── Benchmarks ───────────────────────────────────────────────────────────────

export const listScenarios = () =>
  api.get("/api/benchmark/scenarios").then((r) => r.data);

export const runBenchmark = (scenario, scale, mode) =>
  api.post("/api/benchmark/run", { scenario, scale, mode }).then((r) => r.data);

export const getBenchmarkStatus = (job_id) =>
  api.get(`/api/benchmark/status/${job_id}`).then((r) => r.data);

export const getBenchmarkResults = (job_id) =>
  api.get(`/api/benchmark/results/${job_id}`).then((r) => r.data);

export const listBenchmarkJobs = () =>
  api.get("/api/benchmark/jobs").then((r) => r.data);

// ── Config ───────────────────────────────────────────────────────────────────

export const getConfig = () =>
  api.get("/api/config").then((r) => r.data);
