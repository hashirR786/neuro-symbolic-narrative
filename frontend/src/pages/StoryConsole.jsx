import React, { useEffect, useRef, useState } from "react";
import { generateStory, getHistory, getMetrics } from "../api/client";
import ChatMessage from "../components/ChatMessage";
import ViolationItem from "../components/ViolationItem";

export default function StoryConsole() {
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [stats, setStats] = useState(null);
  const bottomRef = useRef(null);

  async function fetchHistory() {
    try {
      const h = await getHistory();
      setHistory(h);
    } catch {}
  }

  async function fetchStats() {
    try {
      const m = await getMetrics();
      setStats(m);
    } catch {}
  }

  useEffect(() => {
    fetchHistory();
    fetchStats();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  async function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);
    setLastResult(null);

    // Optimistic user message
    setHistory((h) => [...h, { role: "user", content: text }]);

    try {
      const result = await generateStory(text);
      setLastResult(result);
      setHistory((h) => [...h, { role: "assistant", content: result.story_beat }]);
      fetchStats();
    } catch (err) {
      setHistory((h) => [
        ...h,
        { role: "assistant", content: `⚠️ Error: ${err.message || "Backend unreachable."}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  const w = stats?.world || {};
  const violations = lastResult?.violations || [];

  return (
    <div className="flex h-screen">
      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header bar */}
        <div
          className="flex items-center justify-between px-5 py-3 border-b flex-shrink-0"
          style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
        >
          <div>
            <h1 className="text-base font-semibold text-gray-200">Story Console</h1>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Neuro-Symbolic RAG · {stats?.total_steps ?? 0} steps
            </p>
          </div>
          {/* Quick stats */}
          <div className="flex gap-4 text-xs">
            {[
              { label: "Chars", value: w.characters },
              { label: "Items", value: w.items },
              { label: "CS", value: stats?.CS != null ? `${stats.CS}%` : "—" },
              { label: "HR", value: stats?.HR != null ? stats.HR : "—" },
            ].map(({ label, value }) => (
              <div key={label} className="text-center">
                <p className="font-bold text-gray-200">{value ?? "—"}</p>
                <p style={{ color: "var(--text-muted)" }}>{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {history.map((msg, i) => (
            <ChatMessage key={i} role={msg.role} content={msg.content} />
          ))}

          {/* Loading indicator */}
          {loading && (
            <div className="flex gap-3 mb-4">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0"
                style={{ background: "var(--bg-hover)", border: "1px solid var(--border)" }}
              >
                📖
              </div>
              <div
                className="rounded-2xl rounded-tl-sm px-4 py-3"
                style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
              >
                <div className="flex gap-1 items-center h-5">
                  {[0, 0.15, 0.3].map((delay, i) => (
                    <div
                      key={i}
                      className="w-2 h-2 rounded-full animate-pulse"
                      style={{ background: "var(--accent-blue)", animationDelay: `${delay}s` }}
                    />
                  ))}
                  <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    Generating · Extracting · Verifying…
                  </span>
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <form
          onSubmit={handleSubmit}
          className="flex gap-2 px-5 py-4 border-t flex-shrink-0"
          style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="What happens next?"
            disabled={loading}
            className="flex-1 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-1 focus:ring-blue-500"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-5 py-2.5 rounded-xl text-sm font-medium transition-colors disabled:opacity-40"
            style={{ background: "var(--accent-blue)", color: "#fff" }}
          >
            {loading ? "…" : "Send"}
          </button>
        </form>
      </div>

      {/* Right panel — violations + last facts */}
      <aside
        className="w-72 flex-shrink-0 border-l flex flex-col overflow-hidden"
        style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
      >
        <div className="p-4 border-b flex-shrink-0" style={{ borderColor: "var(--border)" }}>
          <h2 className="text-sm font-semibold text-gray-300">⚠️ Last Violations</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          {violations.length === 0 ? (
            <p className="text-xs text-center mt-8" style={{ color: "var(--text-muted)" }}>
              {lastResult ? "✅ No violations detected." : "Violations from the last step appear here."}
            </p>
          ) : (
            violations.map((v, i) => <ViolationItem key={i} violation={v} />)
          )}
        </div>

        {/* Last step facts */}
        {lastResult?.facts?.length > 0 && (
          <>
            <div className="border-t p-3 flex-shrink-0" style={{ borderColor: "var(--border)" }}>
              <p className="text-xs font-semibold text-gray-400 mb-2">
                📋 Facts extracted ({lastResult.facts.length})
              </p>
              <div className="space-y-0.5 max-h-36 overflow-y-auto">
                {lastResult.facts.map((f, i) => (
                  <p key={i} className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                    ({f.subject}, {f.relation}, {f.object})
                  </p>
                ))}
              </div>
            </div>
            <div className="px-3 pb-3 flex-shrink-0">
              <div
                className="rounded-lg px-3 py-2 text-xs"
                style={{
                  background: lastResult.verification_passed ? "#4CAF5022" : "#F4433622",
                  color: lastResult.verification_passed ? "var(--accent-green)" : "var(--accent-red)",
                }}
              >
                {lastResult.verification_passed ? "✅ Verified" : `⚠️ ${lastResult.rewrite_count} rewrite(s)`}
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
