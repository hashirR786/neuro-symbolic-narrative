"""Configuration and model info endpoint."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_config():
    """Return active model, provider, and retrieval settings."""
    provider = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("LLM_MODEL", _default_model(provider))
    return {
        "provider": provider,
        "model": model,
        "retrieval": {
            "faiss_top_k": 3,
            "kg_depth": 2,
            "archive_horizon": 200,
        },
        "verification": {
            "max_retries": 3,
            "rules": [
                "dead_actor",
                "illegal_resurrection",
                "relationship_contradiction",
                "duplicate_ownership",
                "item_transfer_without_exchange",
                "use_without_possession",
                "temporal_dead_actor",
                "location_mismatch",
            ],
        },
        "benchmark_scales": [10, 50, 100],
    }


def _default_model(provider: str) -> str:
    defaults = {
        "ollama": "llama3.2",
        "groq": "llama-3.1-8b-instant",
        "openai": "gpt-4o-mini",
    }
    return defaults.get(provider, "llama3.2")
