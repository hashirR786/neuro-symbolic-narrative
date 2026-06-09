import React, { useState } from "react";

const SEVERITY_COLORS = {
  error:   { icon: "🔴", color: "#F44336" },
  warning: { icon: "🟡", color: "#FF9800" },
};

export default function ViolationItem({ violation }) {
  const [open, setOpen] = useState(false);
  const { icon, color } = SEVERITY_COLORS[violation.severity] || SEVERITY_COLORS.error;
  const rule = violation.rule || "unknown";
  const desc = violation.description || "";
  const step = violation.step_id ?? "?";
  const entities = violation.entities_involved || [];

  return (
    <div
      className="rounded-lg border mb-2 overflow-hidden"
      style={{ borderColor: color + "44", background: "var(--bg-surface)" }}
    >
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-white/5 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <span>{icon}</span>
        <span className="font-mono text-xs px-2 py-0.5 rounded" style={{ background: color + "22", color }}>
          {rule}
        </span>
        <span className="text-gray-400 text-xs">Step {step}</span>
        <span className="flex-1 text-gray-300 text-xs truncate ml-1">{desc.slice(0, 60)}{desc.length > 60 ? "…" : ""}</span>
        <span className="text-gray-500 text-xs ml-auto">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-3 pb-3 pt-1 border-t text-xs space-y-1" style={{ borderColor: "var(--border)" }}>
          <p><span className="text-gray-500">Severity:</span> <span style={{ color }}>{violation.severity}</span></p>
          <p><span className="text-gray-500">Description:</span> <span className="text-gray-300">{desc}</span></p>
          {entities.length > 0 && (
            <p>
              <span className="text-gray-500">Entities: </span>
              {entities.map((e) => (
                <code key={e} className="mr-1">{e}</code>
              ))}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
