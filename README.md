#Neuro-Symbolic RAG — Interactive Narrative Framework

> A local-first, consistency-enforcing storytelling engine that combines **Hybrid RAG retrieval**, **Knowledge Graph reasoning**, and **Symbolic verification** to generate long-form interactive stories free of plot holes, timeline violations, and character contradictions.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://hashirr786-neuro-symbolic-narrative-app-xxxx.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🎯 What Is This?

Most LLMs forget what they said three paragraphs ago. Characters die and come back to life. Items teleport. Timelines collapse.

This framework solves that by wrapping every story generation call in a **three-phase neuro-symbolic pipeline**:

```
Phase 1 — Hybrid Retrieval
  User Input → FAISS Semantic Search + Knowledge Graph Symbolic Search
                                    ↓
Phase 2 — Constrained Generation
  World State + Hard Constraints → LLM Story Generation → Candidate Beat
                                    ↓
Phase 3 — Neuro-Symbolic Verification
  Fact Extraction → Consistency Engine → Pass ✓ / Fail → Self-Correction → Rewrite
                                    ↓
  Commit to FAISS + Knowledge Graph + World State
```

---

## ✨ Features

### 🧠 Knowledge Graph (Dual Graph Architecture)
- **Historical Graph** — every fact ever established, used for retrieval and multi-hop reasoning
- **Current State Graph** — pruned snapshot of latest valid world state, used for clean visualization
- **Automatic archiving** of edges older than 200 steps for scalability at 1000+ turns

### 🌍 World State Manager
- Tracks **characters** (alive/dead, location, health, mood, goals, faction, inventory, relationships)
- Tracks **items** (owner, location, transfer history)
- Tracks **locations**, **events**, **active quests**, and **timeline**
- Injected into every LLM prompt as hard generation constraints

### 🔍 Hybrid Retrieval
- **Dense** — FAISS semantic search over past story segments
- **Symbolic** — multi-hop KG retrieval (up to 2 hops from query entities)
- **Character-centric** — full character dossier pulled before generation
- **World-state injection** — live snapshot + constraint block appended to every prompt

### ✅ Consistency Verifier (8 named rules)
| Layer | Rules |
|---|---|
| Character | Dead actor, illegal resurrection, relationship contradiction |
| Item | Duplicate ownership, transfer without exchange, use without possession |
| Temporal | Action after death (no resurrection), location mismatch |
| World | Configurable hard world rules |

### 🔄 Self-Correction Loop
- Up to 3 rewrite attempts per story beat
- Each retry names the exact violated rules in the correction prompt
- Violation log persisted for dashboard display

### 📊 Evaluation Framework
| Metric | Measures |
|---|---|
| **CS** | Consistency Score — fraction of steps passing all checks (0–100) |
| **KGCS** | KG Consistency Score — contradiction-free edges in the graph (0–100) |
| **TCS** | Temporal Consistency Score — timeline violation rate (0–100) |
| **CCS** | Character Consistency Score — state/relationship checks (0–100) |
| **ICS** | Inventory Consistency Score — ownership/location checks (0–100) |
| **HR** | Hallucination Rate — unsupported entities per step (0–1) |
| **RF** | Rewrite Frequency — avg corrections per step |

### 🗺️ Graph Visualization (6 modes)
- `state` — current world snapshot (default, always readable)
- `character` — relationships and character states only
- `location` — positions and movement
- `inventory` — item ownership
- `event` — major event nodes and causal chains
- `full` — everything in the historical graph

Additional features: Top-N importance filter (degree centrality / PageRank), community detection (greedy modularity), contradiction highlighting in red, entity search, PyVis interactive renderer (optional).

### 🤖 Benchmark Suite (4 canonical scenarios)
| Scenario | Tests |
|---|---|
| Death Barrier | Dead characters must not act |
| Item Transfer | Ownership must update correctly |
| Travel Event | Location must update with movement |
| Relationship Change | Future interactions reflect new relationships |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai) (for local mode) **or** a [Groq API key](https://console.groq.com) (for cloud mode)

### 1. Clone & Install

```bash
git clone https://github.com/hashirR786/neuro-symbolic-narrative.git
cd neuro-symbolic-narrative
pip install -r requirements.txt
```

### 2. Configure LLM Backend

Copy the example env file:

```bash
cp .env.example .env
```

**Option A — Local Ollama (default)**
```bash
# .env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
```
Make sure Ollama is running: `ollama serve` and `ollama pull llama3.2`

**Option B — Groq (fast, free cloud)**
```bash
# .env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
LLM_MODEL=llama-3.1-8b-instant
```
Get a free key at [console.groq.com](https://console.groq.com)

### 3. Run the App

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## 🌐 Cloud Deployment (Streamlit Community Cloud)

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Set **Main file path** to `app.py`
4. Go to **Advanced settings → Secrets** and add:

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "gsk_your_key_here"
LLM_MODEL    = "llama-3.1-8b-instant"
```

5. Click **Deploy** — live in ~2 minutes

> **Why not Vercel?** Vercel is serverless-only and cannot run Streamlit's long-lived process, FAISS, or the sentence-transformer model. Streamlit Community Cloud is the correct deployment target for this stack.

---

## 🗂️ Project Structure

```
neuro-symbolic-narrative/
│
├── app.py                      # Streamlit dashboard
├── requirements.txt
├── .env.example                # Local env template
│
├── src/
│   ├── schema.py               # Pydantic models (Fact, CharacterState, ViolationReport…)
│   ├── world_state.py          # WorldStateManager — live character/item/event tracking
│   ├── kg_manager.py           # Dual KG (historical + state graph) via NetworkX
│   ├── hybrid_retriever.py     # FAISS dense + KG multi-hop + world-state injection
│   ├── verifier.py             # 8-rule consistency engine
│   ├── story_engine.py         # Three-phase pipeline orchestrator
│   ├── llm_manager.py          # Ollama / Groq / OpenAI backend (env-configurable)
│   ├── evaluator.py            # CS/KGCS/TCS/CCS/ICS/HR/RF + CSV/JSON/chart export
│   ├── benchmark.py            # 4-scenario automated benchmark suite
│   └── visualization.py        # GraphView — 6 modes, community detection, PyVis
│
├── tests/
│   └── test_consistency.py     # CLI test runner for all benchmark scenarios
│
└── .streamlit/
    ├── config.toml             # Theme and server config
    └── secrets.toml.example    # Secrets template for Streamlit Cloud
```

---

## 🧪 Running Evaluations

### Quick consistency test (single scenario)

```bash
python -m tests.test_consistency --scenario death_barrier --scale 10
```

### Compare baseline vs neuro-symbolic on all scenarios

```bash
python -m tests.test_consistency --scenario all --scale 10
```

### Full benchmark suite (all scenarios × 10/50/100 steps)

```bash
python -m tests.test_consistency --benchmark
```

Reports are exported to `reports/` as CSV, JSON, and PNG charts.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| LLM (local) | [Ollama](https://ollama.ai) + llama3.2 |
| LLM (cloud) | [Groq](https://groq.com) + llama-3.1-8b-instant |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Dense retrieval | [FAISS](https://github.com/facebookresearch/faiss) |
| Knowledge Graph | [NetworkX](https://networkx.org) MultiDiGraph |
| Schema validation | [Pydantic v2](https://docs.pydantic.dev) |
| Dashboard | [Streamlit](https://streamlit.io) |
| Visualization | Matplotlib + optional [PyVis](https://pyvis.readthedocs.io) |

---

## 📈 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Input                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │        Hybrid Retriever          │
              │  ┌─────────────┐ ┌────────────┐ │
              │  │FAISS Semantic│ │  KG Multi- │ │
              │  │   Memory    │ │ hop Recall  │ │
              │  └─────────────┘ └────────────┘ │
              │         + World State Context    │
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │          LLM Generation          │
              │  (Ollama / Groq / OpenAI)        │
              │  + Hard Constraint Injection     │
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │     Neuro-Symbolic Verifier      │
              │  Character │ Item │ Temporal     │
              │  ──────────┼──────┼──────────    │
              │  Pass ─────┴──────┴──► Commit   │
              │  Fail ──────────────► Rewrite   │
              └────────────────┬────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                   ▼
      Update FAISS       Update KG           Update World
      (semantic)     (historical +          State Manager
                      state graph)
```

---

## 📄 License

MIT — free to use, modify, and deploy.
