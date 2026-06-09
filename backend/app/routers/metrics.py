"""Live metrics endpoints."""

from typing import Optional

from fastapi import APIRouter, Header

from backend.app.session_manager import session_manager

router = APIRouter()


def _resolve(x_session_id: Optional[str]):
    return session_manager.get_or_create(x_session_id or "default")


@router.get("")
async def get_metrics(x_session_id: Optional[str] = Header(default=None)):
    """
    Return all 7 live consistency metrics plus graph health.

    Metrics (preserve exact definitions from story_engine.py / evaluator.py):
      CS   - Consistency Score          (0-100)
      KGCS - KG Consistency Score       (0-100)
      TCS  - Temporal Consistency Score (0-100)
      CCS  - Character Consistency Score(0-100)
      ICS  - Inventory Consistency Score(0-100)
      HR   - Hallucination Rate         (0-1)
      RF   - Rewrite Frequency          (corrections / step)
    """
    data = _resolve(x_session_id)
    engine = data["engine"]

    stats = engine.get_session_stats()
    kgcs = engine.kg.compute_kgcs()
    kg_stats = engine.kg.get_graph_stats()

    return {
        "CS": stats["CS"],
        "KGCS": kgcs,
        "TCS": stats["TCS"],
        "CCS": stats["CCS"],
        "ICS": stats["ICS"],
        "HR": stats["HR"],
        "RF": stats["RF"],
        "total_steps": stats["total_steps"],
        "consistent_steps": stats["consistent_steps"],
        "total_corrections": stats["total_corrections"],
        "graph_health": {
            "historical_nodes": kg_stats["historical_nodes"],
            "historical_edges": kg_stats["historical_edges"],
            "state_nodes": kg_stats["state_nodes"],
            "state_edges": kg_stats["state_edges"],
            "archived_edges": kg_stats["archived_edges"],
            "events": kg_stats["events"],
        },
        "world": {
            "characters": stats["characters"],
            "dead_characters": stats["dead_characters"],
            "items": stats["items"],
            "locations": stats["locations"],
        },
    }
