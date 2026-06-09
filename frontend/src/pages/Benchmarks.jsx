import React, { useEffect, useRef, useState } from "react";
import {
  listScenarios,
  runBenchmark,
  getBenchmarkStatus,
  getBenchmarkResults,
  listBenchmarkJobs,
} from "../api/client";

const SCENARIO_DESCRIPTIONS = {
  death_barrier:       "Arthur dies at step 4 — later prompts attempt to use him.",
  item_transfer:       "Elena transfers an amulet — later attempts to use it herself.",
  travel_event:        "Marcus travels away — later acts from previous location.",
  relationship_change: "Seraphine and Dravec begin as enemies, sign a treaty, then cooperate.",
};

const SCALES = [10, 50, 100];
const MODES  = ["both", "ns", "baseline"];

function MetricCompare({ label, baseline, ns }) {
  if (baseline == null && ns == null) return null;
  const higherIsBetter = !["HR", "RF"].includes(label);
  const nsWins = higherIsBetter ? ns >= baseline : ns <= baseline;
  return (
    <tr className="border-b" style={{ borderColor: "var(--border)" }}>
      <td className="py-2 pr-4 text-xs text-gray-400">{label}</td>
      <td className="py-2 pr-4 text-xs font-mono text-gray-300">{baseline ?? "—"}</td>
      <td className="py-2 text-xs font-mono" style={{ color: nsWins ? "var(--accent-green)" : "var(--accent-red)" }}>
        {ns ?? "—"} {ns != null && baseline != null && (nsWins ? "▲" : "▼")}
      </td>
    </tr>
  );
}

export default function Benchmarks() {
  const [scenarios, setScenarios] = useState({});
  const [selectedScenario, setSelectedScenario] = useState("death_barrier");
  const [scale, setScale] = useState(10);
  const [mode, setMode] = useState("both");
  const [jobs, setJobs] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    listScenarios().then(setScenarios).catch(() => {});
    listBenchmarkJobs().then(setJobs).catch(() => {});
  }, []);

  function startPolling(job_id) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await getBenchmarkStatus(job_id);
        if (status.status === "done") {
          clearInterval(pollRef.current);
          setRunning(false);
          const res = await getBenchmarkResults(job_id);
          setResults(res);
          listBenchmarkJobs().then(setJobs).catch(() => {});
        } else if (status.status === "error") {
          clearInterval(pollRef.current);
          setRunning(false);
          alert(`Benchmark failed: ${status.error}`);
        }
      } catch {}
    }, 3000);
  }

  async function handleRun() {
    setRunning(true);
    setResults(null);
    try {
      const { job_id } = await runBenchmark(selectedScenario, scale, mode);
      setActiveJob(job_id);
      startPolling(job_id);
    } catch (err) {
      setRunning(false);
      alert(`Error starting benchmark: ${err.message}`);
    }
  }

  const METRIC_KEYS = ["CS", "KGCS", "TCS", "CCS", "ICS", "HR", "RF"];

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-gray-100">🧪 Benchmarks</h1>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
          Four canonical consistency scenarios — Death Barrier · Item Transfer · Travel Event · Relationship Change
        </p>
      </div>

      {/* Config panel */}
      <div
        className="rounded-xl border p-5 space-y-4"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
      >
        <h2 className="text-sm font-semibold text-gray-300">Run Configuration</h2>

        {/* Scenario picker */}
        <div>
          <label className="text-xs text-gray-400 block mb-2">Scenario</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {["all", ...Object.keys(SCENARIO_DESCRIPTIONS)].map((s) => (
              <button
                key={s}
                onClick={() => setSelectedScenario(s)}
                className={`text-left rounded-lg border px-3 py-2 text-xs transition-colors ${
                  selectedScenario === s ? "border-blue-500 bg-blue-900/30" : "hover:bg-white/5"
                }`}
                style={{ borderColor: selectedScenario === s ? undefined : "var(--border)" }}
              >
                <p className="font-semibold text-gray-300">{s === "all" ? "🏃 All Scenarios" : s.replace(/_/g, " ")}</p>
                {s !== "all" && (
                  <p className="text-gray-500 mt-0.5">{SCENARIO_DESCRIPTIONS[s]}</p>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Scale + mode */}
        <div className="flex gap-4 flex-wrap">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Scale (steps)</label>
            <div className="flex gap-1">
              {SCALES.map((s) => (
                <button
                  key={s}
                  onClick={() => setScale(s)}
                  className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                    scale === s ? "border-blue-500 bg-blue-900/30 text-blue-300" : "text-gray-400 hover:bg-white/5"
                  }`}
                  style={{ borderColor: scale === s ? undefined : "var(--border)" }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">Mode</label>
            <div className="flex gap-1">
              {MODES.map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                    mode === m ? "border-green-500 bg-green-900/30 text-green-300" : "text-gray-400 hover:bg-white/5"
                  }`}
                  style={{ borderColor: mode === m ? undefined : "var(--border)" }}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={running}
          className="px-6 py-2.5 rounded-xl text-sm font-medium transition-colors disabled:opacity-40"
          style={{ background: "var(--accent-green)", color: "#000" }}
        >
          {running ? "⏳ Running…" : "▶ Run Benchmark"}
        </button>

        {running && (
          <div
            className="rounded-lg px-4 py-2 text-sm animate-pulse"
            style={{ background: "#FF980022", color: "#FF9800" }}
          >
            Benchmark running (job: {activeJob?.slice(0, 8)}…). Polling every 3s…
            <br />
            <span className="text-xs">Scale {scale} may take several minutes with an LLM.</span>
          </div>
        )}
      </div>

      {/* Results */}
      {results && (
        <div
          className="rounded-xl border p-5 space-y-4"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
        >
          <h2 className="text-sm font-semibold text-gray-300">
            Results{results.scenario ? ` — ${results.scenario}` : ""}
          </h2>

          {/* Comparison table (both mode) */}
          {results.baseline && results.neurosymbolic && (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b" style={{ borderColor: "var(--border)" }}>
                    <th className="text-left text-xs text-gray-500 pb-2 pr-4">Metric</th>
                    <th className="text-left text-xs text-gray-500 pb-2 pr-4">Baseline (LLM only)</th>
                    <th className="text-left text-xs text-gray-500 pb-2">Neuro-Symbolic RAG</th>
                  </tr>
                </thead>
                <tbody>
                  {METRIC_KEYS.map((k) => (
                    <MetricCompare
                      key={k}
                      label={k}
                      baseline={results.baseline[k]}
                      ns={results.neurosymbolic[k]}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Single-mode results */}
          {!results.baseline && !results.neurosymbolic && (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
              {METRIC_KEYS.map((k) => (
                results[k] != null && (
                  <div key={k} className="rounded-lg border p-3 text-center" style={{ borderColor: "var(--border)" }}>
                    <p className="text-xl font-bold text-gray-200">{results[k]}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{k}</p>
                  </div>
                )
              ))}
            </div>
          )}

          {/* Aggregate averages (all scenarios) */}
          {results.aggregate_averages && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 mb-2">Aggregate Averages (all scenarios)</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b" style={{ borderColor: "var(--border)" }}>
                      <th className="text-left text-xs text-gray-500 pb-2 pr-4">Metric</th>
                      <th className="text-left text-xs text-gray-500 pb-2 pr-4">Baseline</th>
                      <th className="text-left text-xs text-gray-500 pb-2">Neuro-Symbolic</th>
                    </tr>
                  </thead>
                  <tbody>
                    {METRIC_KEYS.map((k) => (
                      <MetricCompare
                        key={k}
                        label={k}
                        baseline={results.aggregate_averages.baseline?.[k]}
                        ns={results.aggregate_averages.neurosymbolic?.[k]}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Past jobs */}
      {jobs.length > 0 && (
        <div
          className="rounded-xl border p-4"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
        >
          <h2 className="text-sm font-semibold text-gray-300 mb-3">Past Jobs</h2>
          <div className="space-y-1">
            {jobs.map((j) => (
              <div key={j.job_id} className="flex items-center gap-3 text-xs py-1">
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    j.status === "running" ? "animate-pulse bg-yellow-400" :
                    j.status === "done"    ? "bg-green-500" : "bg-red-500"
                  }`}
                />
                <code className="text-gray-500">{j.job_id.slice(0, 8)}</code>
                <span className="text-gray-400">{j.request?.scenario} / n{j.request?.scale}</span>
                <span className="ml-auto text-gray-500">{j.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
