"""
Converts NetworkX graphs (via GraphView) into Cytoscape.js-compatible JSON.

Cytoscape.js element format:
  nodes: [{"data": {"id": str, "label": str, "color": str, ...}}]
  edges: [{"data": {"id": str, "source": str, "target": str, "label": str}}]
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.kg_manager import KGManager
from src.schema import ViolationReport
from src.visualization import GraphView, _PALETTE
from src.world_state import WorldStateManager


def serialize_graph(
    kg: KGManager,
    world_state: Optional[WorldStateManager] = None,
    mode: str = "state",
    top_n: int = 20,
    violations: Optional[List[ViolationReport]] = None,
) -> Dict[str, Any]:
    """Return a Cytoscape.js-ready elements dict plus graph statistics."""
    viol_list = violations or []
    view = GraphView(kg, world_state=world_state, mode=mode, top_n=top_n, violations=viol_list)

    g = view._build_view_graph()
    g = view._apply_top_n(g)

    nodes: List[Dict] = []
    edges: List[Dict] = []

    for node in g.nodes():
        color = view._node_color(node, g)
        label = str(node)
        is_dead = False
        location = None
        health = None

        if world_state and node in world_state.characters:
            char = world_state.characters[node]
            is_dead = not char.is_alive
            location = char.location
            health = char.health
            if is_dead:
                label += "\n[DEAD]"
            elif char.location:
                label += f"\n@{char.location[:12]}"

        item_owner = None
        if world_state and node in world_state.items:
            item_owner = world_state.items[node].owner

        nodes.append({
            "data": {
                "id": str(node),
                "label": label,
                "color": color,
                "isDead": is_dead,
                "location": location,
                "health": health,
                "itemOwner": item_owner,
            }
        })

    for edge_idx, (u, v, data) in enumerate(g.edges(data=True)):
        relation = data.get("relation", "")
        step_id = data.get("step_id", 0)
        is_viol = (
            str(u).lower() in view._violation_entities
            or str(v).lower() in view._violation_entities
        )
        edges.append({
            "data": {
                "id": f"e{edge_idx}",
                "source": str(u),
                "target": str(v),
                "label": relation,
                "stepId": step_id,
                "isViolation": is_viol,
                "color": _PALETTE["violation"] if is_viol else "#4a5568",
            }
        })

    communities = view.get_communities()

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": kg.get_graph_stats(),
        "communities": communities,
        "mode": mode,
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
    }
