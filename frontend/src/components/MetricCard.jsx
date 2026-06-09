import React from "react";

/**
 * A metric display card matching the Streamlit _big_metric() style.
 *
 * Props:
 *   label       : string  e.g. "CS — Consistency Score"
 *   value       : number | string
 *   unit        : string  e.g. "/ 100" or "(lower is better)"
 *   progress    : number 0–1 (optional — omit for HR/RF)
 *   color       : CSS colour for the progress bar
 *   description : optional subtitle
 */
export default function MetricCard({
  label,
  value,
  unit = "/ 100",
  progress = null,
  color = "#4CAF50",
  description,
}) {
  return (
    <div
      className="rounded-xl p-4 border"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
    >
      <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>
        {label}
      </p>
      <div className="flex items-baseline gap-1 mb-2">
        <span className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>
          {typeof value === "number" && Number.isFinite(value) ? value : value ?? "—"}
        </span>
        <span className="text-sm" style={{ color: "var(--text-muted)" }}>{unit}</span>
      </div>

      {progress !== null && (
        <div className="metric-bar mt-1">
          <div
            className="metric-bar-fill"
            style={{
              width: `${Math.min(100, Math.max(0, progress * 100)).toFixed(1)}%`,
              background: color,
            }}
          />
        </div>
      )}

      {description && (
        <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
          {description}
        </p>
      )}
    </div>
  );
}
