import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMetrics, getRecentFacts, getWorldState } from "../api/client";

function StatChip({ icon, label, value, color }) {
  return (
    <div
      className="flex items-center gap-3 rounded-xl px-4 py-3 border"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
    >
      <span className="text-2xl">{icon}</span>
      <div>
        <p className="text-2xl font-bold" style={{ color }}>{value ?? "—"}</p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</p>
      </div>
    </div>
  );
}

function MetricMini({ label, value, color, progress }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-xs">
        <span style={{ color: "var(--text-muted)" }}>{label}</span>
        <span className="font-semibold" style={{ color }}>{value ?? "—"}</span>
      </div>
      <div className="metric-bar">
        <div className="metric-bar-fill" style={{ width: `${progress ?? 0}%`, background: color }} />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [facts, setFacts] = useState([]);
  const [world, setWorld] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [m, f, w] = await Promise.all([getMetrics(), getRecentFacts(10), getWorldState()]);
      setMetrics(m);
      setFacts(f.facts || []);
      setWorld(w);
    } catch {
      // Backend may not be ready — silently retry
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const m = metrics || {};
  const w = m.world || {};

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">📖 Dashboard</h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
          Hybrid FAISS + Knowledge Graph retrieval · Symbolic verification · Live world-state tracking
        </p>
      </div>

      {/* Stat chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatChip icon="🧑" label="Characters"  value={w.characters}      color="var(--accent-green)" />
        <StatChip icon="🗡️" label="Items"       value={w.items}           color="var(--accent-orange)" />
        <StatChip icon="📍" label="Locations"    value={world?.locations?.length ?? "—"} color="var(--accent-blue)" />
        <StatChip icon="📝" label="Story Steps"  value={m.total_steps}     color="var(--accent-purple)" />
      </div>

      {/* Metrics mini panel */}
      <div
        className="rounded-xl border p-5"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">Live Consistency Metrics</h2>
          <Link to="/metrics" className="text-xs text-blue-400 hover:text-blue-300">View all →</Link>
        </div>
        {loading ? (
          <p className="text-xs text-gray-500">Loading…</p>
        ) : m.total_steps === 0 ? (
          <p className="text-xs text-gray-500">No story steps yet — head to Story Console to begin.</p>
        ) : (
          <div className="space-y-3">
            <MetricMini label="CS — Consistency Score"        value={m.CS}   color="var(--accent-green)"  progress={m.CS} />
            <MetricMini label="KGCS — KG Consistency Score"   value={m.KGCS} color="var(--accent-blue)"   progress={m.KGCS} />
            <MetricMini label="TCS — Temporal Consistency"    value={m.TCS}  color="var(--accent-orange)" progress={m.TCS} />
            <MetricMini label="CCS — Character Consistency"   value={m.CCS}  color="var(--accent-purple)" progress={m.CCS} />
            <MetricMini label="ICS — Inventory Consistency"   value={m.ICS}  color="var(--accent-red)"    progress={m.ICS} />
          </div>
        )}
      </div>

      {/* Two-column: recent facts + quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Recent KG facts */}
        <div
          className="rounded-xl border p-4"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
        >
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-300">📋 Recent KG Facts</h2>
            <Link to="/graph" className="text-xs text-blue-400 hover:text-blue-300">Graph →</Link>
          </div>
          {facts.length === 0 ? (
            <p className="text-xs text-gray-500">No facts yet.</p>
          ) : (
            <div className="space-y-1 max-h-52 overflow-y-auto">
              {facts.map((f, i) => (
                <code key={i} className="block text-xs truncate">{f}</code>
              ))}
            </div>
          )}
        </div>

        {/* Quick links */}
        <div
          className="rounded-xl border p-4"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
        >
          <h2 className="text-sm font-semibold text-gray-300 mb-3">⚡ Quick Actions</h2>
          <div className="space-y-2">
            {[
              { to: "/story",      icon: "💬", label: "Open Story Console",       desc: "Continue the narrative" },
              { to: "/graph",      icon: "🔵", label: "Explore Knowledge Graph",   desc: "Visualise entity relationships" },
              { to: "/world",      icon: "🌍", label: "Inspect World State",       desc: "Character & item dossiers" },
              { to: "/benchmarks", icon: "🧪", label: "Run Benchmarks",           desc: "Test consistency scenarios" },
            ].map(({ to, icon, label, desc }) => (
              <Link
                key={to}
                to={to}
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-white/5 transition-colors border"
                style={{ borderColor: "var(--border)" }}
              >
                <span>{icon}</span>
                <div>
                  <p className="text-gray-300 font-medium text-xs">{label}</p>
                  <p className="text-gray-500 text-xs">{desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Dead characters warning */}
      {world?.characters && Object.values(world.characters).some((c) => !c.is_alive) && (
        <div
          className="rounded-xl border px-4 py-3 flex items-center gap-3 text-sm"
          style={{ borderColor: "#F44336" + "44", background: "#F4433611" }}
        >
          <span>💀</span>
          <span className="text-red-300">
            {Object.values(world.characters).filter((c) => !c.is_alive).length} dead character(s) tracked in world state.
            The verifier will prevent them from acting.
          </span>
        </div>
      )}
    </div>
  );
}
