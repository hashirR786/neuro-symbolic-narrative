import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { initSession } from "./api/client";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import StoryConsole from "./pages/StoryConsole";
import KnowledgeGraph from "./pages/KnowledgeGraph";
import WorldState from "./pages/WorldState";
import Benchmarks from "./pages/Benchmarks";
import Metrics from "./pages/Metrics";
import Settings from "./pages/Settings";

export default function App() {
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionError, setSessionError] = useState(null);

  useEffect(() => {
    initSession()
      .then(() => setSessionReady(true))
      .catch((err) => setSessionError(err.message));
  }, []);

  if (sessionError) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-navy-800">
        <div className="text-center p-8 rounded-xl border border-red-500/30 bg-navy-700 max-w-md">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-red-400 mb-2">Backend Unreachable</h2>
          <p className="text-gray-400 text-sm mb-4">
            Could not connect to the FastAPI backend.
          </p>
          <code className="block text-xs bg-navy-900 rounded p-3 text-left text-green-400">
            uvicorn backend.main:app --reload
          </code>
          <p className="text-gray-500 text-xs mt-3">{sessionError}</p>
        </div>
      </div>
    );
  }

  if (!sessionReady) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-navy-800">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-pulse">📖</div>
          <p className="text-gray-400">Initialising session…</p>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"     element={<Dashboard />} />
          <Route path="story"         element={<StoryConsole />} />
          <Route path="graph"         element={<KnowledgeGraph />} />
          <Route path="world"         element={<WorldState />} />
          <Route path="benchmarks"    element={<Benchmarks />} />
          <Route path="metrics"       element={<Metrics />} />
          <Route path="settings"      element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
