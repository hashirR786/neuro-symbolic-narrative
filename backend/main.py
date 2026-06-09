"""
FastAPI backend for the Neuro-Symbolic RAG Interactive Narrative system.

Run from the project root (where src/ lives):
    uvicorn backend.main:app --reload --port 8000

Environment variables (see .env.example):
    ALLOWED_ORIGINS   : comma-separated list of allowed CORS origins
    LLM_PROVIDER      : ollama | groq | openai
    LLM_MODEL         : model name override
    GROQ_API_KEY      : required when LLM_PROVIDER=groq
"""

import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import story, metrics, graph, benchmark, session, config

app = FastAPI(
    title="Neuro-Symbolic RAG API",
    description="Production API for the Neuro-Symbolic Interactive Narrative system",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_origins_env = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
)
origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(session.router,   prefix="/api/session",   tags=["session"])
app.include_router(story.router,     prefix="/api/story",     tags=["story"])
app.include_router(metrics.router,   prefix="/api/metrics",   tags=["metrics"])
app.include_router(graph.router,     prefix="/api/graph",     tags=["graph"])
app.include_router(benchmark.router, prefix="/api/benchmark", tags=["benchmark"])
app.include_router(config.router,    prefix="/api/config",    tags=["config"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
