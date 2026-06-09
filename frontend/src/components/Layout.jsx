import React from "react";
import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/dashboard",  icon: "🏠", label: "Dashboard" },
  { to: "/story",      icon: "📖", label: "Story Console" },
  { to: "/graph",      icon: "🔵", label: "Knowledge Graph" },
  { to: "/world",      icon: "🌍", label: "World State" },
  { to: "/metrics",    icon: "📊", label: "Metrics" },
  { to: "/benchmarks", icon: "🧪", label: "Benchmarks" },
  { to: "/settings",   icon: "⚙️",  label: "Settings" },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-primary)" }}>
      {/* Sidebar */}
      <aside
        className="w-56 flex-shrink-0 flex flex-col border-r"
        style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
      >
        {/* Logo */}
        <div className="px-4 py-5 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="text-2xl mb-1">📖</div>
          <p className="text-xs font-semibold text-gray-300 leading-tight">
            Neuro-Symbolic RAG
          </p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Interactive Narrative
          </p>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-3 space-y-0.5 px-2">
          {NAV.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-blue-900/40 text-blue-300 font-medium"
                    : "text-gray-400 hover:text-gray-200 hover:bg-white/5"
                }`
              }
            >
              <span className="text-base">{icon}</span>
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t text-xs" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
          <p>FAISS + KG Retrieval</p>
          <p>Symbolic Verification</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto" style={{ background: "var(--bg-primary)" }}>
        <Outlet />
      </main>
    </div>
  );
}
