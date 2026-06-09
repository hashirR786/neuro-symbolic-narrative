import React, { useCallback, useEffect, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import cytoscape from "cytoscape";
import coseBilkent from "cytoscape-cose-bilkent";
import { getCurrentGraph, getEntityFacts, searchEntities } from "../api/client";

// Register layout extension once
cytoscape.use(coseBilkent);

const MODES = ["state", "character", "location", "inventory", "event", "full"];
const TOP_N_OPTIONS = [20, 50, 100, 0];

function cyStylesheet() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "background-color": "data(color)",
        "font-size": "9px",
        "text-valign": "center",
        "text-halign": "center",
        color: "#fff",
        "text-wrap": "wrap",
        "text-max-width": "80px",
        width: 40,
        height: 40,
        "border-width": 2,
        "border-color": "#30363d",
        "font-family": "JetBrains Mono, monospace",
      },
    },
    {
      selector: "node:selected",
      style: { "border-color": "#fff", "border-width": 3 },
    },
    {
      selector: "edge",
      style: {
        label: "data(label)",
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "target-arrow-color": "data(color)",
        "line-color": "data(color)",
        "font-size": "7px",
        color: "#8b949e",
        "text-background-color": "#0d1117",
        "text-background-opacity": 0.7,
        "text-background-padding": "2px",
        width: 1.5,
      },
    },
    {
      selector: "edge[isViolation = 'true']",
      style: { "line-style": "dashed", width: 2.5 },
    },
  ];
}

export default function KnowledgeGraph() {
  const [graphData, setGraphData] = useState(null);
  const [mode, setMode] = useState("state");
  const [topN, setTopN] = useState(20);
  const [highlightViolations, setHighlightViolations] = useState(true);
  const [loading, setLoading] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [entityFacts, setEntityFacts] = useState(null);
  const cyRef = useRef(null);

  async function fetchGraph() {
    setLoading(true);
    try {
      const data = await getCurrentGraph(mode, topN, highlightViolations);
      setGraphData(data);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { fetchGraph(); }, [mode, topN, highlightViolations]);

  async function handleSearch() {
    if (!searchQ.trim()) return;
    try {
      const { matches } = await searchEntities(searchQ);
      setSearchResults(matches);
    } catch {}
  }

  async function handleSelectEntity(name) {
    setSelectedEntity(name);
    try {
      const data = await getEntityFacts(name);
      setEntityFacts(data);
    } catch {}
    // Highlight node in graph
    if (cyRef.current) {
      cyRef.current.elements().removeClass("highlighted");
      const node = cyRef.current.getElementById(name);
      if (node) node.addClass("highlighted");
    }
  }

  const elements = graphData
    ? [
        ...graphData.nodes.map((n) => ({ data: { ...n.data, isViolation: String(false) } })),
        ...graphData.edges.map((e) => ({ data: { ...e.data, isViolation: String(e.data.isViolation) } })),
      ]
    : [];

  const isEmpty = !graphData || graphData.nodeCount === 0;

  return (
    <div className="p-5 space-y-4 h-screen flex flex-col">
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-gray-100">🔵 Knowledge Graph</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            {graphData ? `${graphData.nodeCount} nodes · ${graphData.edgeCount} edges · ${mode} view` : "Loading…"}
          </p>
        </div>
        <button
          onClick={fetchGraph}
          className="text-xs px-3 py-1.5 rounded-lg border transition-colors hover:bg-white/5"
          style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
        >
          ↻ Refresh
        </button>
      </div>

      {/* Controls */}
      <div
        className="flex flex-wrap gap-3 items-center p-3 rounded-xl border flex-shrink-0"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-400">View</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            className="text-xs rounded-lg px-2 py-1.5 outline-none"
            style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-400">Top N</label>
          <select
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
            className="text-xs rounded-lg px-2 py-1.5 outline-none"
            style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            {TOP_N_OPTIONS.map((n) => (
              <option key={n} value={n}>{n === 0 ? "All" : n}</option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
          <input
            type="checkbox"
            checked={highlightViolations}
            onChange={(e) => setHighlightViolations(e.target.checked)}
            className="rounded"
          />
          Highlight violations
        </label>

        {loading && (
          <span className="text-xs animate-pulse" style={{ color: "var(--text-muted)" }}>Updating…</span>
        )}
      </div>

      {/* Graph */}
      <div className="flex-1 flex gap-4 min-h-0">
        <div className="flex-1 cy-container relative">
          {isEmpty ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-gray-500 text-sm">Graph is empty — start the story to populate it.</p>
            </div>
          ) : (
            <CytoscapeComponent
              elements={elements}
              stylesheet={cyStylesheet()}
              style={{ width: "100%", height: "100%" }}
              layout={{ name: "cose-bilkent", animate: true, animationDuration: 500, nodeDimensionsIncludeLabels: true }}
              cy={(cy) => {
                cyRef.current = cy;
                cy.on("tap", "node", (evt) => {
                  handleSelectEntity(evt.target.id());
                });
              }}
            />
          )}
        </div>

        {/* Right panel: search + entity details */}
        <div className="w-64 flex-shrink-0 flex flex-col gap-3">
          {/* Entity search */}
          <div
            className="rounded-xl border p-3"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
          >
            <p className="text-xs font-semibold text-gray-400 mb-2">🔍 Entity Search</p>
            <div className="flex gap-1">
              <input
                type="text"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Name…"
                className="flex-1 text-xs rounded-lg px-2 py-1.5 outline-none"
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              />
              <button
                onClick={handleSearch}
                className="text-xs px-2 py-1.5 rounded-lg"
                style={{ background: "var(--accent-blue)", color: "#fff" }}
              >
                Go
              </button>
            </div>
            {searchResults.length > 0 && (
              <div className="mt-2 space-y-0.5 max-h-32 overflow-y-auto">
                {searchResults.map((name) => (
                  <button
                    key={name}
                    onClick={() => handleSelectEntity(name)}
                    className="w-full text-left text-xs px-2 py-1 rounded hover:bg-white/5 text-gray-300"
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Entity details */}
          {entityFacts && (
            <div
              className="rounded-xl border p-3 flex-1 overflow-y-auto"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
            >
              <p className="text-xs font-semibold text-gray-300 mb-2">
                Facts for <code>{selectedEntity}</code>
              </p>
              {entityFacts.facts.length === 0 ? (
                <p className="text-xs text-gray-500">No facts found.</p>
              ) : (
                <div className="space-y-0.5">
                  {entityFacts.facts.slice(0, 30).map((f, i) => (
                    <code key={i} className="block text-xs break-all">{f}</code>
                  ))}
                </div>
              )}
              {entityFacts.world_state_context && (
                <div className="mt-3 pt-3 border-t text-xs text-gray-400 whitespace-pre-wrap" style={{ borderColor: "var(--border)" }}>
                  {entityFacts.world_state_context}
                </div>
              )}
            </div>
          )}

          {/* Graph stats */}
          {graphData?.stats && (
            <div
              className="rounded-xl border p-3"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
            >
              <p className="text-xs font-semibold text-gray-400 mb-2">Graph Statistics</p>
              <div className="space-y-1 text-xs">
                {Object.entries(graphData.stats).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span style={{ color: "var(--text-muted)" }}>{k}</span>
                    <span className="text-gray-300 font-mono">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
