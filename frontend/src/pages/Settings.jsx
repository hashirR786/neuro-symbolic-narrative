import React, { useEffect, useState } from "react";
import { getConfig, resetSession } from "../api/client";

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between py-2.5 border-b text-sm" style={{ borderColor: "var(--border)" }}>
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <code className="text-gray-300">{value ?? "—"}</code>
    </div>
  );
}

export default function Settings() {
  const [config, setConfig] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [resetDone, setResetDone] = useState(false);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => {});
  }, []);

  async function handleReset() {
    if (!confirm("Reset the story session? All story history, world state, and KG facts will be cleared.")) return;
    setResetting(true);
    try {
      await resetSession();
      setResetDone(true);
      setTimeout(() => setResetDone(false), 3000);
    } catch {}
    setResetting(false);
  }

  const sid = localStorage.getItem("nsrag_session_id");

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-gray-100">⚙️ Settings</h1>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
          Active configuration — model and session management
        </p>
      </div>

      {/* Model config */}
      <div
        className="rounded-xl border p-5"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
      >
        <h2 className="text-sm font-semibold text-gray-300 mb-3">LLM Configuration</h2>
        {config ? (
          <>
            <InfoRow label="Provider"      value={config.provider} />
            <InfoRow label="Model"         value={config.model} />
            <InfoRow label="FAISS top-k"   value={config.retrieval?.faiss_top_k} />
            <InfoRow label="KG depth"      value={config.retrieval?.kg_depth} />
            <InfoRow label="Archive horizon" value={config.retrieval?.archive_horizon} />
            <InfoRow label="Max retries"   value={config.verification?.max_retries} />
          </>
        ) : (
          <p className="text-xs text-gray-500">Loading config…</p>
        )}
      </div>

      {/* Verification rules */}
      {config?.verification?.rules && (
        <div
          className="rounded-xl border p-5"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
        >
          <h2 className="text-sm font-semibold text-gray-300 mb-3">8-Rule Verification Engine</h2>
          <div className="grid grid-cols-2 gap-2">
            {config.verification.rules.map((rule) => (
              <div key={rule} className="flex items-center gap-2 text-xs">
                <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent-green)" }} />
                <code className="text-gray-300">{rule}</code>
              </div>
            ))}
          </div>
          <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
            All rules are enforced by <code>ConsistencyVerifier</code>. Failed facts trigger up to{" "}
            {config.verification.max_retries} self-correction rewrites before committing.
          </p>
        </div>
      )}

      {/* Session management */}
      <div
        className="rounded-xl border p-5"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
      >
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Session Management</h2>
        <InfoRow label="Session ID" value={sid ? sid.slice(0, 16) + "…" : "none"} />

        <div className="mt-4 flex gap-3 flex-wrap">
          <button
            onClick={handleReset}
            disabled={resetting}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-40"
            style={{ background: "#F4433622", color: "#F44336", border: "1px solid #F4433644" }}
          >
            {resetting ? "Resetting…" : "🔄 Reset Session"}
          </button>

          {resetDone && (
            <span className="text-sm px-3 py-2 rounded-lg" style={{ background: "#4CAF5022", color: "var(--accent-green)" }}>
              ✅ Session reset — start a new story!
            </span>
          )}
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
          Resetting clears all story history, FAISS index, Knowledge Graph, and world state. The session ID is preserved.
        </p>
      </div>

      {/* Architecture info */}
      <div
        className="rounded-xl border p-5 space-y-3"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
      >
        <h2 className="text-sm font-semibold text-gray-300">Architecture</h2>
        {[
          { label: "Phase 1", desc: "Hybrid Retrieval — FAISS semantic + KG multi-hop BFS (depth 2)" },
          { label: "Phase 2", desc: "LLM Generation via OpenAI-compatible client (Groq / Ollama)" },
          { label: "Phase 3", desc: "Neuro-Symbolic Verification — 8 rules · up to 3 self-correction retries" },
          { label: "KG", desc: "Dual NetworkX graph: Historical MultiDiGraph + State DiGraph + Archive" },
          { label: "WorldState", desc: "Pydantic-typed character & item state, updated atomically after verification" },
        ].map(({ label, desc }) => (
          <div key={label} className="flex gap-3 text-xs">
            <code className="flex-shrink-0 font-semibold" style={{ color: "var(--accent-blue)", minWidth: "72px" }}>
              {label}
            </code>
            <span style={{ color: "var(--text-muted)" }}>{desc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
