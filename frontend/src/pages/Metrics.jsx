import React, { useEffect, useState } from "react";
import { getMetrics, getViolations, clearViolations } from "../api/client";
import MetricCard from "../components/MetricCard";
import ViolationItem from "../components/ViolationItem";

export default function Metrics() {
  const [metrics, setMetrics] = useState(null);
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [m, v] = await Promise.all([getMetrics(), getViolations()]);
      setMetrics(m);
      setViolations(v.violations || []);
    } catch {}
    setLoading(false);
  }

  async function handleClear() {
    await clearViolations();
    setViolations([]);
  }

  useEffect(() => { load(); }, []);

  const m = metrics || {};
  const gh = m.graph_health || {};

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-100">📊 Metrics</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            Live consistency monitoring · {m.total_steps ?? 0} steps
          </p>
        </div>
        <button
          onClick={load}
          className="text-xs px-3 py-1.5 rounded-lg border hover:bg-white/5"
          style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
        >
          ↻ Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : m.total_steps === 0 ? (
        <div
          className="rounded-xl border p-8 text-center"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
        >
          <p className="text-gray-500">No story steps yet — start the story to see live metrics.</p>
        </div>
      ) : (
        <>
          {/* Main metric cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            <MetricCard
              label="CS — Consistency Score"
              value={m.CS}
              progress={m.CS / 100}
              color="var(--accent-green)"
            />
            <MetricCard
              label="KGCS — KG Consistency"
              value={m.KGCS}
              progress={m.KGCS / 100}
              color="var(--accent-blue)"
            />
            <MetricCard
              label="TCS — Temporal"
              value={m.TCS}
              progress={m.TCS / 100}
              color="var(--accent-orange)"
            />
            <MetricCard
              label="CCS — Character"
              value={m.CCS}
              progress={m.CCS / 100}
              color="var(--accent-purple)"
            />
            <MetricCard
              label="ICS — Inventory"
              value={m.ICS}
              progress={m.ICS / 100}
              color="var(--accent-red)"
            />
            <MetricCard
              label="HR — Hallucination Rate"
              value={m.HR}
              unit="(lower is better)"
              description="Fraction of facts referencing unknown entities"
            />
            <MetricCard
              label="RF — Rewrite Frequency"
              value={typeof m.RF === "number" ? m.RF.toFixed(2) : "—"}
              unit="corrections / step"
              description="Average verify-rewrite cycles per story step"
            />
          </div>

          {/* Constraint reminder */}
          <div
            className="rounded-xl border p-3 text-xs"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border)", color: "var(--text-muted)" }}
          >
            <p>
              <strong className="text-gray-300">Metric constraint:</strong>{" "}
              CS ≤ min(TCS, CCS, ICS) &nbsp;·&nbsp;
              TCS / CCS / ICS are layer-specific breakdowns and are not redefined.
            </p>
            <p className="mt-1">
              <strong className="text-gray-300">Steps:</strong> {m.total_steps} total · {m.consistent_steps} consistent ·{" "}
              {m.total_corrections} total corrections
            </p>
          </div>

          {/* Graph health */}
          <div
            className="rounded-xl border p-4"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
          >
            <h2 className="text-sm font-semibold text-gray-300 mb-3">Graph Health</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              {[
                { label: "Historical nodes", value: gh.historical_nodes },
                { label: "Historical edges", value: gh.historical_edges },
                { label: "Archived edges",   value: gh.archived_edges },
                { label: "State nodes",      value: gh.state_nodes },
                { label: "State edges",      value: gh.state_edges },
                { label: "Dead characters",  value: m.world?.dead_characters },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between border-b pb-2" style={{ borderColor: "var(--border)" }}>
                  <span style={{ color: "var(--text-muted)" }}>{label}</span>
                  <span className="font-mono text-gray-300">{value ?? "—"}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Violations log */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-300">
            ⚠️ Contradiction Log ({violations.length})
          </h2>
          {violations.length > 0 && (
            <button
              onClick={handleClear}
              className="text-xs px-3 py-1.5 rounded-lg border hover:bg-white/5"
              style={{ borderColor: "#F4433644", color: "#F44336" }}
            >
              Clear log
            </button>
          )}
        </div>

        {violations.length === 0 ? (
          <div
            className="rounded-xl border p-4 text-center text-xs"
            style={{ background: "#4CAF5011", borderColor: "#4CAF5044", color: "var(--accent-green)" }}
          >
            ✅ No violations detected so far.
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto space-y-1">
            {[...violations].reverse().map((v, i) => (
              <ViolationItem key={i} violation={v} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
