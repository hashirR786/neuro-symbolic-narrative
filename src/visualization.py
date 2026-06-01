"""
Visualization module — dual-graph, layered views, community detection, importance filtering.

Graph modes
───────────
  "state"     — Current State Graph (default, lightweight, only latest facts)
  "character" — Characters + relationships only
  "location"  — Locations + character positions
  "inventory" — Item ownership edges
  "event"     — Major event nodes + participant edges
  "full"      — All nodes and edges in the historical graph

Importance filtering
────────────────────
  Top-N nodes by degree centrality, betweenness centrality, or PageRank.

Community detection
───────────────────
  Uses networkx greedy_modularity_communities (no extra deps required).
  Falls back to connected components if the graph is too small.

Output
──────
  * render_matplotlib() → matplotlib Figure  (always available)
  * render_pyvis()      → HTML string        (requires pyvis)

Contradiction highlighting
──────────────────────────
  Pass a list of ViolationReport objects; the involved entity nodes are
  rendered in red with a dashed border.
"""

from __future__ import annotations

import logging
import textwrap
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from src.kg_manager import KGManager
from src.schema import ViolationReport

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False
    logger.warning("matplotlib not installed — render_matplotlib() unavailable.")

try:
    from pyvis.network import Network as PyvisNetwork
    _PYVIS_AVAILABLE = True
except ImportError:
    _PYVIS_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# Node-type colour palette
# ──────────────────────────────────────────────────────────────────────────────

_PALETTE: Dict[str, str] = {
    "character": "#4CAF50",   # green
    "location":  "#2196F3",   # blue
    "item":      "#FF9800",   # orange
    "event":     "#9C27B0",   # purple
    "entity":    "#78909C",   # grey (unknown type)
    "dead":      "#F44336",   # red
    "violation": "#FF1744",   # bright red
}

_LOCATION_KEYWORDS = {"castle", "village", "forest", "city", "port", "isle",
                       "dungeon", "mountain", "tower", "palace", "camp", "cave"}
_ITEM_KEYWORDS     = {"sword", "amulet", "ring", "potion", "shield", "staff",
                       "bow", "axe", "key", "map", "scroll", "gem", "coin"}


# ──────────────────────────────────────────────────────────────────────────────
# GraphView — main facade
# ──────────────────────────────────────────────────────────────────────────────

class GraphView:
    """Prepares and renders a filtered, annotated view of the knowledge graph."""

    def __init__(
        self,
        kg: KGManager,
        world_state=None,           # WorldStateManager | None
        mode: str = "state",        # see module docstring
        top_n: int = 0,             # 0 = no limit
        violations: Optional[List[ViolationReport]] = None,
    ) -> None:
        self.kg = kg
        self.world_state = world_state
        self.mode = mode
        self.top_n = top_n
        self.violations = violations or []
        self._violation_entities: Set[str] = {
            e.lower() for v in self.violations for e in v.entities_involved
        }

    # ------------------------------------------------------------------
    # Public rendering API
    # ------------------------------------------------------------------

    def render_matplotlib(
        self,
        figsize: Tuple[int, int] = (10, 8),
        title: str = "",
    ) -> "plt.Figure":
        """Render the selected graph view as a matplotlib Figure."""
        if not _MPL_AVAILABLE:
            raise RuntimeError("matplotlib is not installed.")

        g = self._build_view_graph()
        if g.number_of_nodes() == 0:
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, "Graph is empty.", ha="center", va="center",
                    fontsize=14, color="grey")
            ax.set_axis_off()
            return fig

        g = self._apply_top_n(g)
        communities = self._detect_communities(g)
        node_colors = self._compute_node_colors(g, communities)
        pos = self._compute_layout(g)
        edge_labels = self._edge_labels(g)

        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(title or f"Knowledge Graph — {self.mode} view", fontsize=13, pad=12)

        # Draw edges first
        nx.draw_networkx_edges(
            g, pos, ax=ax,
            arrows=True, arrowstyle="->", arrowsize=12,
            edge_color="#BDBDBD", width=1.2,
        )

        # Violation edges in red
        if self._violation_entities:
            viol_edges = [
                (u, v) for u, v in g.edges()
                if u.lower() in self._violation_entities or v.lower() in self._violation_entities
            ]
            if viol_edges:
                nx.draw_networkx_edges(
                    g, pos, edgelist=viol_edges, ax=ax,
                    edge_color=_PALETTE["violation"], width=2.0,
                    arrows=True, arrowstyle="->", arrowsize=14,
                    style="dashed",
                )

        # Draw nodes
        nx.draw_networkx_nodes(g, pos, ax=ax, node_color=node_colors, node_size=800, alpha=0.92)

        # Labels — wrap long names
        wrapped = {n: "\n".join(textwrap.wrap(str(n), 12)) for n in g.nodes()}
        nx.draw_networkx_labels(g, pos, labels=wrapped, ax=ax, font_size=8, font_weight="bold")

        # Edge labels (truncated)
        short_labels = {k: v[:12] for k, v in edge_labels.items()}
        nx.draw_networkx_edge_labels(
            g, pos, edge_labels=short_labels, ax=ax, font_size=7, alpha=0.8
        )

        # Legend
        legend_patches = [
            mpatches.Patch(color=c, label=lbl)
            for lbl, c in _PALETTE.items()
            if lbl not in {"entity"}
        ]
        ax.legend(handles=legend_patches, loc="upper left", fontsize=8, framealpha=0.8)
        ax.set_axis_off()
        plt.tight_layout()
        return fig

    def render_pyvis(self, height: str = "600px", width: str = "100%") -> str:
        """Render the view as an interactive PyVis HTML string."""
        if not _PYVIS_AVAILABLE:
            raise RuntimeError(
                "pyvis is not installed.  Run: pip install pyvis"
            )
        g = self._build_view_graph()
        g = self._apply_top_n(g)

        net = PyvisNetwork(height=height, width=width, directed=True,
                           notebook=False, bgcolor="#1a1a2e", font_color="white")
        net.set_options("""{
          "physics": {"enabled": true, "solver": "barnesHut",
                      "barnesHut": {"gravitationalConstant": -8000}},
          "interaction": {"hover": true, "navigationButtons": true, "zoomView": true}
        }""")

        for node in g.nodes():
            color = self._node_color(node, g)
            title = self._node_tooltip(node)
            net.add_node(str(node), label=str(node), color=color,
                         title=title, size=20)

        for u, v, data in g.edges(data=True):
            rel = data.get("relation", "")
            step = data.get("step_id", "")
            color = _PALETTE["violation"] if (
                str(u).lower() in self._violation_entities
                or str(v).lower() in self._violation_entities
            ) else "#BDBDBD"
            net.add_edge(str(u), str(v), label=rel, title=f"Step {step}",
                         color=color, arrows="to")

        return net.generate_html()

    def get_communities(self) -> Dict[str, int]:
        """Return {node: community_id} mapping for the current view."""
        g = self._build_view_graph()
        communities = self._detect_communities(g)
        result = {}
        for comm_id, members in enumerate(communities):
            for m in members:
                result[m] = comm_id
        return result

    def get_centrality(self, method: str = "degree") -> Dict[str, float]:
        """Return centrality scores for nodes in the current view."""
        g = self._build_view_graph()
        if g.number_of_nodes() == 0:
            return {}
        ug = g.to_undirected()
        if method == "betweenness":
            return nx.betweenness_centrality(ug)
        elif method == "pagerank":
            return nx.pagerank(g, alpha=0.85) if g.number_of_edges() > 0 else {}
        else:
            return nx.degree_centrality(ug)

    # ------------------------------------------------------------------
    # Graph construction per mode
    # ------------------------------------------------------------------

    def _build_view_graph(self) -> nx.DiGraph:
        mode = self.mode.lower()
        if mode == "state":
            return self._as_simple_digraph(self.kg.state_graph)
        elif mode == "character":
            return self._filter_by_relation(
                self.kg.state_graph,
                {"friendOf", "enemyOf", "alliedWith", "partnerOf", "marriedTo",
                 "rivalOf", "isAlive", "health"},
            )
        elif mode == "location":
            return self._filter_by_relation(
                self.kg.historical_graph if hasattr(self.kg, "historical_graph")
                else self.kg.graph,
                {"locatedIn", "locatedAt", "movesTo", "travels"},
            )
        elif mode == "inventory":
            return self._filter_by_relation(
                self.kg.historical_graph if hasattr(self.kg, "historical_graph")
                else self.kg.graph,
                {"hasItem", "owns", "carries", "dropped", "gave"},
            )
        elif mode == "event":
            return self._build_event_graph()
        else:  # "full"
            return self._as_simple_digraph(self.kg.graph)

    def _filter_by_relation(self, source: nx.Graph, allowed_relations: Set[str]) -> nx.DiGraph:
        g = nx.DiGraph()
        allowed_lower = {r.lower() for r in allowed_relations}
        for u, v, data in source.edges(data=True):
            if data.get("relation", "").lower() in allowed_lower:
                g.add_node(u)
                g.add_node(v)
                g.add_edge(u, v, **data)
        return g

    def _build_event_graph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        event_ids = {e.event_id for e in self.kg.events}
        for node, attrs in self.kg.graph.nodes(data=True):
            if attrs.get("type") == "event" or node in event_ids:
                g.add_node(node, **attrs)
        for u, v, data in self.kg.graph.edges(data=True):
            if u in g.nodes or v in g.nodes:
                g.add_node(u)
                g.add_node(v)
                g.add_edge(u, v, **data)
        return g

    def _as_simple_digraph(self, source: nx.Graph) -> nx.DiGraph:
        """Convert MultiDiGraph → DiGraph keeping only the latest edge per (u, v, rel)."""
        g = nx.DiGraph()
        for node, attrs in source.nodes(data=True):
            g.add_node(node, **attrs)
        seen: Dict[Tuple, int] = {}
        best_data: Dict[Tuple, Dict] = {}
        for u, v, data in source.edges(data=True):
            rel = data.get("relation", "")
            step = data.get("step_id", 0)
            key = (str(u), str(v), rel)
            if key not in seen or step > seen[key]:
                seen[key] = step
                best_data[key] = data
        for (u, v, _), data in best_data.items():
            g.add_edge(u, v, **data)
        return g

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _apply_top_n(self, g: nx.DiGraph) -> nx.DiGraph:
        if self.top_n <= 0 or g.number_of_nodes() <= self.top_n:
            return g
        centrality = nx.degree_centrality(g.to_undirected())
        top_nodes = sorted(centrality, key=centrality.get, reverse=True)[: self.top_n]
        return g.subgraph(top_nodes).copy()

    # ------------------------------------------------------------------
    # Community detection
    # ------------------------------------------------------------------

    def _detect_communities(self, g: nx.Graph):
        if g.number_of_nodes() < 3:
            return [{n} for n in g.nodes()]
        ug = g.to_undirected()
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            return list(greedy_modularity_communities(ug))
        except Exception:
            return list(nx.connected_components(ug))

    # ------------------------------------------------------------------
    # Visual helpers
    # ------------------------------------------------------------------

    def _compute_node_colors(self, g: nx.DiGraph, communities) -> List[str]:
        colors = []
        for node in g.nodes():
            colors.append(self._node_color(node, g))
        return colors

    def _node_color(self, node: str, g: nx.DiGraph) -> str:
        n = str(node).lower()
        if n in self._violation_entities:
            return _PALETTE["violation"]
        if self.world_state:
            if node in self.world_state.characters:
                char = self.world_state.characters[node]
                return _PALETTE["dead"] if not char.is_alive else _PALETTE["character"]
            if node in self.world_state.items:
                return _PALETTE["item"]
            if node in self.world_state.locations:
                return _PALETTE["location"]
        ntype = g.nodes[node].get("type", "entity") if g.has_node(node) else "entity"
        if ntype == "event":
            return _PALETTE["event"]
        if any(kw in n for kw in _LOCATION_KEYWORDS):
            return _PALETTE["location"]
        if any(kw in n for kw in _ITEM_KEYWORDS):
            return _PALETTE["item"]
        return _PALETTE["character"] if n[0].isupper() else _PALETTE["entity"]

    def _compute_layout(self, g: nx.DiGraph) -> Dict[str, Any]:
        n = g.number_of_nodes()
        if n == 0:
            return {}
        if n < 30:
            return nx.spring_layout(g, k=1.2, iterations=60, seed=42)
        return nx.kamada_kawai_layout(g)

    def _edge_labels(self, g: nx.DiGraph) -> Dict[Tuple, str]:
        return {
            (u, v): data.get("relation", "")
            for u, v, data in g.edges(data=True)
        }

    def _node_tooltip(self, node: str) -> str:
        if self.world_state and node in self.world_state.characters:
            char = self.world_state.characters[node]
            return (
                f"<b>{node}</b><br>"
                f"Alive: {char.is_alive}<br>"
                f"Location: {char.location or '?'}<br>"
                f"Health: {char.health}<br>"
                f"Inventory: {', '.join(char.inventory) or 'none'}"
            )
        if self.world_state and node in self.world_state.items:
            item = self.world_state.items[node]
            return f"<b>{node}</b><br>Owner: {item.owner or 'none'}<br>Location: {item.location or '?'}"
        return f"<b>{node}</b>"


# ──────────────────────────────────────────────────────────────────────────────
# Convenience functions for use in app.py
# ──────────────────────────────────────────────────────────────────────────────

def build_figure(
    kg: KGManager,
    world_state=None,
    mode: str = "state",
    top_n: int = 0,
    violations: Optional[List[ViolationReport]] = None,
    figsize: Tuple[int, int] = (9, 7),
) -> "plt.Figure":
    """One-call helper — returns a matplotlib Figure for Streamlit st.pyplot()."""
    view = GraphView(kg, world_state=world_state, mode=mode,
                     top_n=top_n, violations=violations)
    return view.render_matplotlib(figsize=figsize)


def build_pyvis_html(
    kg: KGManager,
    world_state=None,
    mode: str = "state",
    top_n: int = 0,
    violations: Optional[List[ViolationReport]] = None,
) -> str:
    """One-call helper — returns PyVis HTML string for Streamlit components.html()."""
    view = GraphView(kg, world_state=world_state, mode=mode,
                     top_n=top_n, violations=violations)
    return view.render_pyvis()
