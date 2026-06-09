"""Knowledge Graph visualization and query endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Header, Query

from backend.app.graph_serializer import serialize_graph
from backend.app.session_manager import session_manager

router = APIRouter()

_VALID_MODES = {"state", "character", "location", "inventory", "event", "full"}


def _resolve(x_session_id: Optional[str]):
    return session_manager.get_or_create(x_session_id or "default")


@router.get("/current")
async def get_current_graph(
    mode: str = Query(default="state", description="View mode: state|character|location|inventory|event|full"),
    top_n: int = Query(default=20, description="Max nodes to show (0 = all)"),
    highlight_violations: bool = Query(default=True),
    x_session_id: Optional[str] = Header(default=None),
):
    """
    Return the current-state knowledge graph as Cytoscape.js elements.
    Uses GraphView with the requested mode to filter and annotate nodes.
    """
    data = _resolve(x_session_id)
    engine = data["engine"]

    if mode not in _VALID_MODES:
        mode = "state"

    violations = engine.last_violations if highlight_violations else []

    graph_data = serialize_graph(
        kg=engine.kg,
        world_state=engine.world_state,
        mode=mode,
        top_n=top_n,
        violations=violations,
    )
    return graph_data


@router.get("/historical")
async def get_historical_graph(
    top_n: int = Query(default=50),
    x_session_id: Optional[str] = Header(default=None),
):
    """Return the full historical graph (all facts ever added)."""
    data = _resolve(x_session_id)
    engine = data["engine"]

    graph_data = serialize_graph(
        kg=engine.kg,
        world_state=engine.world_state,
        mode="full",
        top_n=top_n,
    )
    return graph_data


@router.get("/stats")
async def get_graph_stats(x_session_id: Optional[str] = Header(default=None)):
    """Return raw graph statistics."""
    data = _resolve(x_session_id)
    engine = data["engine"]
    stats = engine.kg.get_graph_stats()
    kgcs = engine.kg.compute_kgcs()
    return {**stats, "KGCS": kgcs}


@router.get("/entity/{name}")
async def get_entity_facts(
    name: str,
    x_session_id: Optional[str] = Header(default=None),
):
    """Return all KG facts for a named entity (2-hop BFS)."""
    data = _resolve(x_session_id)
    engine = data["engine"]
    facts = engine.kg.get_character_context(name)
    ws_context = (
        engine.world_state.get_character_context(name)
        if name in engine.world_state.characters
        else None
    )
    return {
        "entity": name,
        "facts": facts,
        "world_state_context": ws_context,
        "in_graph": engine.kg.graph.has_node(name),
    }


@router.get("/search")
async def search_entities(
    q: str = Query(..., description="Search term"),
    x_session_id: Optional[str] = Header(default=None),
):
    """Return KG nodes whose name contains the query string."""
    data = _resolve(x_session_id)
    engine = data["engine"]
    q_lower = q.lower()
    matches = [
        str(n) for n in engine.kg.graph.nodes()
        if q_lower in str(n).lower()
    ]
    return {"query": q, "matches": matches}
