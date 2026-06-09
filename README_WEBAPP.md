# Neuro-Symbolic RAG — Web Application

Production-ready React + FastAPI conversion of the Streamlit research dashboard.
The entire neuro-symbolic pipeline (FAISS, NetworkX, verification engine, WorldState) is preserved unchanged.

---

## Project Structure

```
project/
├── backend/               # FastAPI backend
│   ├── main.py            # App entry point
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── session_manager.py   # StoryEngine lifecycle per session
│       ├── graph_serializer.py  # NetworkX → Cytoscape.js JSON
│       └── routers/
│           ├── session.py
│           ├── story.py
│           ├── metrics.py
│           ├── graph.py
│           ├── benchmark.py
│           └── config.py
│
├── frontend/              # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js
│   │   ├── components/
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       ├── StoryConsole.jsx
│   │       ├── KnowledgeGraph.jsx
│   │       ├── WorldState.jsx
│   │       ├── Metrics.jsx
│   │       ├── Benchmarks.jsx
│   │       └── Settings.jsx
│   ├── package.json
│   └── vite.config.js
│
├── src/                   # Original pipeline (UNCHANGED)
│   ├── story_engine.py
│   ├── kg_manager.py
│   ├── world_state.py
│   ├── verifier.py
│   ├── hybrid_retriever.py
│   ├── llm_manager.py
│   ├── visualization.py
│   ├── evaluator.py
│   └── benchmark.py
│
└── app.py                 # Original Streamlit app (preserved)
```

---

## Local Development

### 1. Backend

```bash
# From the project root (where src/ lives)
pip install -r backend/requirements.txt

# Copy and configure environment
cp backend/.env.example .env
# Edit .env: set LLM_PROVIDER, GROQ_API_KEY, etc.

# Start the API server
uvicorn backend.main:app --reload --port 8000
```

The backend runs at http://localhost:8000
API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at http://localhost:5173 and proxies `/api` to the backend automatically.

---

## API Reference

### Session

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/session/new` | Create a new story session |
| GET | `/api/session/info` | Get session info |
| POST | `/api/session/reset` | Reset session (clears engine + history) |
| DELETE | `/api/session/` | Delete session |

All story/metrics/graph endpoints require the `X-Session-ID` header.

### Story

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/story/generate` | Generate next story beat |
| GET | `/api/story/history` | Full chat history |
| GET | `/api/story/state` | Current world state |
| GET | `/api/story/violations` | Accumulated violation log |
| GET | `/api/story/facts?n=30` | Recent KG facts |

### Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/metrics` | CS, KGCS, TCS, CCS, ICS, HR, RF |

### Knowledge Graph

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/graph/current?mode=state&top_n=20` | Current-state graph (Cytoscape.js JSON) |
| GET | `/api/graph/historical?top_n=50` | Full historical graph |
| GET | `/api/graph/stats` | Raw graph statistics |
| GET | `/api/graph/entity/{name}` | Entity facts (2-hop BFS) |
| GET | `/api/graph/search?q=Arthur` | Entity name search |

### Benchmarks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/benchmark/scenarios` | List scenarios |
| POST | `/api/benchmark/run` | Start benchmark (async) |
| GET | `/api/benchmark/status/{job_id}` | Poll job status |
| GET | `/api/benchmark/results/{job_id}` | Get completed results |

---

## Deployment

### Backend — Render / Railway

1. Set root directory to the project root (not `backend/`)
2. Build command: `pip install -r backend/requirements.txt`
3. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Set environment variables:
   - `LLM_PROVIDER`, `LLM_MODEL`, `GROQ_API_KEY`
   - `ALLOWED_ORIGINS=https://your-frontend.vercel.app`

### Frontend — Vercel

1. Set root directory to `frontend/`
2. Build command: `npm run build`
3. Output directory: `dist`
4. Set environment variable:
   - `VITE_API_URL=https://your-backend.onrender.com`

---

## Architecture

```
User Input
    │
    ▼
Phase 1 — Hybrid Retrieval
    ├── FAISS: top-k semantic chunks
    └── KG: depth-2 BFS around entities
    ▼
Phase 2 — LLM Generation (Groq / Ollama)
    ▼
Phase 3 — Neuro-Symbolic Verification
    ├── LLM fact extraction → structured triples
    ├── 8-rule consistency engine
    │   ├── Character: dead-actor, illegal-resurrection, relationship-contradiction
    │   ├── Item: duplicate-ownership, transfer-without-exchange, use-without-possession
    │   └── Temporal: action-after-death, location-mismatch
    ├── Pass → commit to FAISS + KG + WorldState
    └── Fail → self-correction prompt (up to 3 retries)
```

## Metrics Constraint

```
CS ≤ min(TCS, CCS, ICS)
```

TCS, CCS, and ICS are per-layer breakdowns of CS and are not redefined.
