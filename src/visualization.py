"""
Visualization module — clean, readable graph rendering.

Key improvements over v1:
  - Scalar value nodes (true/false/contentment/etc.) never rendered — stored as node attrs
  - Long-string nodes (sentence fragments) filtered out
  - kamada_kawai_layout for medium graphs, spring for small
  - Node labels show entity name + key attributes (alive status, location)
  - Tooltips show full attribute dict
  - Community detection for colour grouping
  - Default Top-20 in state view
"""

from __future__ import annotations

import logging
import textwrap
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from src.kg_manager import KGManager, _MAX_LABEL_LEN, _VALUE_WORDS
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

try:
    from pyvis.network import Network as PyvisNetwork
    _PYVIS_AVAILABLE = True
except ImportError:
    _PYVIS_AVAILABLE = False

# ── Colour palette ─────────────────────────────────────────────────────────────
_PALETTE: Dict[str, str] = {
    "character": "#4CAF50",
    "location":  "#2196F3",
    "item":      "#FF9800",
    "event":     "#9C27B0",
    "entity":    "#78909C",
    "dead":      "#F44336",
    "violation": "#FF1744",
}

_LOCATION_KEYWORDS = {
    "castle", "village", "forest", "city", "port", "isle", "dungeon",
    "mountain", "tower", "palace", "camp", "cave", "school", "office",
    "hallway", "room", "street", "park", "hall", "gate", "gates",
    "hospital", "market", "shop", "house", "home", "lab",
}
_ITEM_KEYWORDS = {
    "sword", "amulet", "ring", "potion", "shield", "staff", "bow",
    "axe", "key", "map", "scroll", "gem", "coin", "book", "note",
    "phone", "bag", "knife", "gun", "wand",
}


class GraphView:
    """Prepares and renders a filtered, annotated view of the knowledge graph."""

    def __init__(
        self,
        kg: KGManager,
        world_state=None,
        mode: str = "state",
        top_n: int = 20,
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
        if not _MPL_AVAILABLE:
            raise RuntimeError("matplotlib is not installed.")

        g = self._build_view_graph()

        if g.number_of_nodes() == 0:
            fig, ax = plt.subplots(figsize=figsize)
            ax.set_facecolor("#1a1a2e")
            fig.patch.set_facecolor("#1a1a2e")
            ax.text(0.5, 0.5, "Graph is empty — start the story to populate it.",
                    ha="center", va="center", fontsize=13, color="#8b949e")
            ax.set_axis_off()
            return fig

        g = self._apply_top_n(g)
        node_colors  = [self._node_color(n, g) for n in g.nodes()]
        node_sizes   = [self._node_size(n, g) for n in g.nodes()]
        pos          = self._compute_layout(g)
        labels       = self._node_labels(g)
        edge_labels  = {(u, v): data.get("relation", "")
                        for u, v, data in g.edges(data=True)}

        fig, ax = plt.subplots(figsize=figsize)
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#1a1a2e")
        ax.set_title(
            title or f"Knowledge Graph — {self.mode} view",
            fontsize=13, color="white", pad=12,
        )

        # Draw edges
        normal_edges = [
            (u, v) for u, v in g.edges()
            if u.lower() not in self._violation_entities
            and v.lower() not in self._violation_entities
        ]
        viol_edges = [
            (u, v) for u, v in g.edges()
            if u.lower() in self._violation_entities
            or v.lower() in self._violation_entities
        ]

        if normal_edges:
            nx.draw_networkx_edges(
                g, pos, edgelist=normal_edges, ax=ax,
                arrows=True, arrowstyle="->", arrowsize=14,
                edge_color="#4a5568", width=1.5, alpha=0.8,
            )
        if viol_edges:
            nx.draw_networkx_edges(
                g, pos, edgelist=viol_edges, ax=ax,
                arrows=True, arrowstyle="->", arrowsize=16,
                edge_color=_PALETTE["violation"], width=2.5,
                style="dashed", alpha=0.9,
            )

        # Draw nodes
        nx.draw_networkx_nodes(
            g, pos, ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.95,
        )

        # Node labels
        nx.draw_networkx_labels(
            g, pos, labels=labels, ax=ax,
            font_size=8, font_color="white", font_weight="bold",
        )

        # Edge labels (truncated)
        short_edge_labels = {k: v[:14] for k, v in edge_labels.items()}
        nx.draw_networkx_edge_labels(
            g, pos, edge_labels=short_edge_labels, ax=ax,
            font_size=7, font_color="#a0aec0", alpha=0.85,
            bbox=dict(boxstyle="round,pad=0.2", fc="#1a1a2e", alpha=0.6, ec="none"),
        )

        # Legend
        legend_patches = [
            mpatches.Patch(color=c, label=lbl)
            for lbl, c in _PALETTE.items()
            if lbl not in {"entity"}
        ]
        ax.legend(
            handles=legend_patches, loc="upper left",
            fontsize=8, framealpha=0.4,
            facecolor="#0d1117", labelcolor="white",
        )
        ax.set_axis_off()
        plt.tight_layout()
        return fig

    def render_pyvis(self, height: str = "600px", width: str = "100%") -> str:
        if not _PYVIS_AVAILABLE:
            raise RuntimeError("pyvis is not installed. Run: pip install pyvis")

        g = self._build_view_graph()
        g = self._apply_top_n(g)

        net = PyvisNetwork(
            height=height, width=width, directed=True,
            notebook=False, bgcolor="#1a1a2e", font_color="white",
        )
        net.set_options("""{
          "physics": {"enabled": true, "solver": "forceAtlas2Based",
                      "forceAtlas2Based": {"gravitationalConstant": -60,
                                           "springLength": 120}},
          "interaction": {"hover": true, "navigationButtons": true, "zoomView": true},
          "edges": {"smooth": {"type": "dynamic"}}
        }""")

        for node in g.nodes():
            color = self._node_color(node, g)
            title = self._node_tooltip(node, g)
            label = self._short_label(node, g)
            net.add_node(str(node), label=label, color=color,
                         title=title, size=22, font={"color": "white"})

        for u, v, data in g.edges(data=True):
            rel = data.get("relation", "")
            is_viol = (str(u).lower() in self._violation_entities
                       or str(v).lower() in self._violation_entities)
            color = _PALETTE["violation"] if is_viol else "#4a5568"
            net.add_edge(str(u), str(v), label=rel, color=color,
                         arrows="to", font={"color": "#a0aec0", "size": 9})

        return net.generate_html()

    def get_communities(self) -> Dict[str, int]:
        g = self._build_view_graph()
        communities = self._detect_communities(g)
        result = {}
        for comm_id, members in enumerate(communities):
            for m in members:
                result[m] = comm_id
        return result

    def get_centrality(self, method: str = "degree") -> Dict[str, float]:
        g = self._build_view_graph()
        if g.number_of_nodes() == 0:
            return {}
        ug = g.to_undirected()
        if method == "betweenness":
            return nx.betweenness_centrality(ug)
        elif method == "pagerank":
            return nx.pagerank(g, alpha=0.85) if g.number_of_edges() > 0 else {}
        return nx.degree_centrality(ug)

    # ------------------------------------------------------------------
    # Graph construction per mode
    # ------------------------------------------------------------------

    def _build_view_graph(self) -> nx.DiGraph:
        mode = self.mode.lower()
        if mode == "state":
            return self._clean_state_graph()
        elif mode == "character":
            return self._filter_by_relation(
                self.kg.state_graph,
                {"friendOf", "enemyOf", "alliedWith", "partnerOf",
                 "marriedTo", "rivalOf"},
            )
        elif mode == "location":
            return self._filter_by_relation(
                self.kg.graph,
                {"locatedIn", "locatedAt", "movesTo", "travels", "isin"},
            )
        elif mode == "inventory":
            return self._filter_by_relation(
                self.kg.graph,
                {"hasItem", "owns", "carries", "dropped", "gave"},
            )
        elif mode == "event":
            return self._build_event_graph()
        else:  # full
            return self._as_simple_digraph(self.kg.graph)

    def _clean_state_graph(self) -> nx.DiGraph:
        """
        Return the state graph with all value/sentence-fragment nodes removed.
        Only keep nodes that are genuine entities (short proper-noun-style names).
        """
        g = nx.DiGraph()
        for node, attrs in self.kg.state_graph.nodes(data=True):
            if not self._is_junk_node(str(node)):
                g.add_node(node, **attrs)

        for u, v, data in self.kg.state_graph.edges(data=True):
            if g.has_node(u) and g.has_node(v):
                g.add_edge(u, v, **data)
        return g

    def _filter_by_relation(self, source: nx.Graph, allowed: Set[str]) -> nx.DiGraph:
        allowed_lower = {r.lower() for r in allowed}
        g = nx.DiGraph()
        for u, v, data in source.edges(data=True):
            if data.get("relation", "").lower() in allowed_lower:
                if not self._is_junk_node(str(u)) and not self._is_junk_node(str(v)):
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
            if g.has_node(u) or g.has_node(v):
                if not self._is_junk_node(str(u)) and not self._is_junk_node(str(v)):
                    g.add_node(u)
                    g.add_node(v)
                    g.add_edge(u, v, **data)
        return g

    def _as_simple_digraph(self, source: nx.Graph) -> nx.DiGraph:
        g = nx.DiGraph()
        for node, attrs in source.nodes(data=True):
            if not self._is_junk_node(str(node)):
                g.add_node(node, **attrs)
        seen: Dict[Tuple, int] = {}
        best_data: Dict[Tuple, Dict] = {}
        for u, v, data in source.edges(data=True):
            if not g.has_node(u) or not g.has_node(v):
                continue
            rel  = data.get("relation", "")
            step = data.get("step_id", 0)
            key  = (str(u), str(v), rel)
            if key not in seen or step > seen[key]:
                seen[key] = step
                best_data[key] = data
        for (u, v, _), data in best_data.items():
            g.add_edge(u, v, **data)
        return g

    # ------------------------------------------------------------------
    # Filtering helpers
    # ------------------------------------------------------------------

    def _is_junk_node(self, name: str) -> bool:
        """True if this node should be hidden from visualization."""
        if name.lower() in _VALUE_WORDS:
            return True
        if len(name) > _MAX_LABEL_LEN:
            return True
        if name.count(" ") > 4:
            return True
        # Starts lowercase and has spaces → likely a sentence fragment
        if " " in name and name[0].islower() and len(name) > 15:
            return True
        return False

    def _apply_top_n(self, g: nx.DiGraph) -> nx.DiGraph:
        if self.top_n <= 0 or g.number_of_nodes() <= self.top_n:
            return g
        centrality = nx.degree_centrality(g.to_undirected())
        top_nodes  = sorted(centrality, key=centrality.get, reverse=True)[: self.top_n]
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

    def _compute_layout(self, g: nx.DiGraph) -> Dict:
        n = g.number_of_nodes()
        if n == 0:
            return {}
        if n <= 6:
            return nx.spring_layout(g, k=2.5, iterations=80, seed=42)
        if n <= 30:
            try:
                return nx.kamada_kawai_layout(g)
            except Exception:
                pass
        return nx.spring_layout(g, k=1.8, iterations=100, seed=42)

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
        if n[0].isupper() if node else False:
            return _PALETTE["character"]
        return _PALETTE["entity"]

    def _node_size(self, node: str, g: nx.DiGraph) -> int:
        deg = g.degree(node)
        return min(300 + deg * 80, 1800)

    def _node_labels(self, g: nx.DiGraph) -> Dict[str, str]:
        """Short readable label: name + alive badge if dead."""
        labels = {}
        for node in g.nodes():
            label = "\n".join(textwrap.wrap(str(node), 12))
            if self.world_state and node in self.world_state.characters:
                char = self.world_state.characters[node]
                if not char.is_alive:
                    label += "\n[DEAD]"
                elif char.location:
                    short_loc = char.location[:10]
                    label += f"\n@{short_loc}"
            labels[node] = label
        return labels

    def _short_label(self, node: str, g: nx.DiGraph) -> str:
        label = str(node)
        if self.world_state and node in self.world_state.characters:
            char = self.world_state.characters[node]
            if not char.is_alive:
                label += " [DEAD]"
        return label

    def _node_tooltip(self, node: str, g: nx.DiGraph) -> str:
        lines = [f"<b>{node}</b>"]
        # Node attributes (scalars stored by KGManager)
        attrs = g.nodes[node] if g.has_node(node) else {}
        skip = {"type", "last_updated_step"}
        for k, v in attrs.items():
            if k not in skip and v:
                lines.append(f"{k}: {v}")
        # WorldState info
        if self.world_state:
            if node in self.world_state.characters:
                char = self.world_state.characters[node]
                lines += [
                    f"Alive: {char.is_alive}",
                    f"Location: {char.location or '?'}",
                    f"Health: {char.health}",
                    f"Inventory: {', '.join(char.inventory) or 'none'}",
                ]
            elif node in self.world_state.items:
                item = self.world_state.items[node]
                lines.append(f"Owner: {item.owner or 'none'}")
                lines.append(f"Location: {item.location or '?'}")
        return "<br>".join(lines)


# ── Convenience functions for app.py ──────────────────────────────────────────

def build_figure(
    kg: KGManager,
    world_state=None,
    mode: str = "state",
    top_n: int = 20,
    violations: Optional[List[ViolationReport]] = None,
    figsize: Tuple[int, int] = (9, 7),
) -> "plt.Figure":
    view = GraphView(kg, world_state=world_state, mode=mode,
                     top_n=top_n, violations=violations)
    return view.render_matplotlib(figsize=figsize)


def build_pyvis_html(
    kg: KGManager,
    world_state=None,
    mode: str = "state",
    top_n: int = 20,
    violations: Optional[List[ViolationReport]] = None,
) -> str:
    view = GraphView(kg, world_state=world_state, mode=mode,
                     top_n=top_n, violations=violations)
    return view.render_pyvis()
