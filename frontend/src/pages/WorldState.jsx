import React, { useEffect, useState } from "react";
import { getWorldState } from "../api/client";

function CharacterCard({ name, char }) {
  const [open, setOpen] = useState(false);
  const alive = char.is_alive;

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{ borderColor: alive ? "var(--border)" : "#F4433644", background: "var(--bg-surface)" }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-white/5 transition-colors"
      >
        <span className="text-lg">{alive ? "🧑" : "💀"}</span>
        <span className="font-semibold text-sm text-gray-200">{name}</span>
        {!alive && (
          <span className="text-xs px-2 py-0.5 rounded-full ml-1" style={{ background: "#F4433622", color: "#F44336" }}>
            DEAD
          </span>
        )}
        {char.location && (
          <span className="text-xs text-gray-500 ml-auto">📍 {char.location}</span>
        )}
        <span className="text-gray-500 text-xs ml-2">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t text-sm" style={{ borderColor: "var(--border)" }}>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Alive</p>
              <p className="text-gray-300">{alive ? "Yes" : "No"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Location</p>
              <p className="text-gray-300">{char.location || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Health</p>
              <p className="text-gray-300">{char.health || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Faction</p>
              <p className="text-gray-300">{char.faction || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Mood</p>
              <p className="text-gray-300">{char.emotional_state || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-0.5">Goals</p>
              <p className="text-gray-300">{char.goals?.join(", ") || "—"}</p>
            </div>
          </div>
          {char.inventory?.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-gray-500 mb-1">Inventory</p>
              <div className="flex flex-wrap gap-1">
                {char.inventory.map((item) => (
                  <span key={item} className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#FF980022", color: "#FF9800" }}>
                    🗡️ {item}
                  </span>
                ))}
              </div>
            </div>
          )}
          {char.relationships && Object.keys(char.relationships).length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-gray-500 mb-1">Relationships</p>
              <div className="space-y-0.5">
                {Object.entries(char.relationships).map(([other, rel]) => (
                  <p key={other} className="text-xs text-gray-300">
                    <span className="text-gray-400">{other}</span>
                    <span className="mx-1 text-gray-500">→</span>
                    <em className="text-blue-300">{rel}</em>
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function WorldState() {
  const [ws, setWs] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const data = await getWorldState();
      setWs(data);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  if (loading) {
    return <div className="p-6 text-gray-500">Loading world state…</div>;
  }

  const empty = !ws || (Object.keys(ws.characters || {}).length === 0 && Object.keys(ws.items || {}).length === 0);

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-100">🌍 World State</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            Step {ws?.current_step ?? 0} · Authoritative character & item snapshot
          </p>
        </div>
        <button
          onClick={load}
          className="text-xs px-3 py-1.5 rounded-lg border transition-colors hover:bg-white/5"
          style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
        >
          ↻ Refresh
        </button>
      </div>

      {empty ? (
        <div
          className="rounded-xl border p-8 text-center"
          style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
        >
          <p className="text-gray-500">World state is empty. Start the story to populate it.</p>
        </div>
      ) : (
        <>
          {/* Characters */}
          {Object.keys(ws?.characters || {}).length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3">
                Characters ({Object.keys(ws.characters).length})
              </h2>
              <div className="space-y-2">
                {Object.entries(ws.characters).map(([name, char]) => (
                  <CharacterCard key={name} name={name} char={char} />
                ))}
              </div>
            </section>
          )}

          {/* Items */}
          {Object.keys(ws?.items || {}).length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3">
                Items ({Object.keys(ws.items).length})
              </h2>
              <div
                className="rounded-xl border p-4"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
              >
                <div className="space-y-2">
                  {Object.entries(ws.items).map(([name, item]) => (
                    <div key={name} className="flex items-center gap-3 text-sm">
                      <span className="text-lg">🗡️</span>
                      <span className="font-medium text-gray-200">{name}</span>
                      <span className="text-gray-500 text-xs">
                        owned by <em className="text-gray-300">{item.owner || "nobody"}</em>
                        {item.location ? ` · at ${item.location}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Locations */}
          {ws?.locations?.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3">
                Known Locations ({ws.locations.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {ws.locations.map((loc) => (
                  <span
                    key={loc}
                    className="text-xs px-3 py-1.5 rounded-full border"
                    style={{ borderColor: "#2196F344", background: "#2196F311", color: "#2196F3" }}
                  >
                    📍 {loc}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Timeline */}
          {ws?.timeline?.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3">Timeline</h2>
              <div
                className="rounded-xl border p-4 max-h-48 overflow-y-auto"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
              >
                {[...ws.timeline].reverse().slice(0, 20).map((entry, i) => (
                  <div key={i} className="flex items-center gap-3 py-1 text-xs border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                    <span className="text-gray-500 font-mono w-14">Step {entry.step}</span>
                    <span className="text-gray-400">{entry.facts_applied} facts applied</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Active quests */}
          {ws?.active_quests?.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-400 mb-3">Active Quests</h2>
              <div className="flex flex-wrap gap-2">
                {ws.active_quests.map((q) => (
                  <span key={q} className="text-xs px-3 py-1 rounded-full" style={{ background: "#9C27B022", color: "#9C27B0" }}>
                    ⚔️ {q}
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
