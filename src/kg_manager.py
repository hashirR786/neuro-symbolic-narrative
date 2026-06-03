"""
KGManager — NetworkX-based dual Knowledge Graph.

  historical_graph : MultiDiGraph  — every fact ever added, used for retrieval and reasoning.
  state_graph      : DiGraph        — entity-only graph for clean visualization.

Key design decision for clean visualization:
  Scalar relations (isAlive, health, feels, faction, goal, wantsTo) are stored as
  NODE ATTRIBUTES on the subject node in the state_graph, NOT as separate connected nodes.
  Only entity-to-entity relations (locatedIn, hasItem, friendOf, attacks, etc.) become edges.
  This prevents value strings like "true", "false", "contentment" from polluting the graph.
"""

import logging
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from src.schema import Fact, EventNode

logger = logging.getLogger(__name__)

# WHITELIST — only these relations produce entity-to-entity edges in the state graph.
# Every other relation is stored as a node ATTRIBUTE (no edge, no value node).
_ENTITY_RELATIONS: frozenset = frozenset({
    # Movement / location
    "locatedin", "locatedat", "isin", "presentat", "movesto", "travels",
    # Inventory
    "hasitem", "owns", "carries", "pickedup", "holds", "dropped", "gave", "transfers",
    # Interpersonal
    "friendof", "enemyof", "alliedwith", "partnerof", "marriedto",
    "rivalof", "servantof", "masterof", "memberof",
    # Actions (character → character)
    "attacks", "kills", "rescues", "speaks", "commands", "helps",
    # Event graph
    "participatedin", "occurredat", "causes",
})

# Maximum character length for a node label shown in state graph
_MAX_LABEL_LEN: int = 28

# Exact strings that are clearly scalar values — never rendered as nodes
_VALUE_WORDS: frozenset = frozenset({
    "true", "false", "yes", "no", "dead", "alive",
    "unknown", "none", "null", "0", "1",
    "open", "closed", "locked", "unlocked",
})

# Prefixes that flag a phrase as a description, not an entity name
_DESC_PREFIXES: tuple = ("her ", "his ", "their ", "the ", "a ", "an ",
                          "my ", "our ", "its ")


class KGManager:
    """Manages the dual Knowledge Graph using NetworkX."""

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self.state_graph: nx.DiGraph = nx.DiGraph()
        self.current_step: int = 0
        self.events: List[EventNode] = []
        self.archive_graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self.archive_horizon: int = 200

    # ------------------------------------------------------------------
    # Core write API
    # ------------------------------------------------------------------

    def add_facts(self, facts: List[Fact]) -> None:
        """Add a list of facts, updating both historical and state graphs."""
        self.current_step += 1

        for fact in facts:
            fact.step_id = self.current_step
            subj = fact.subject.strip()
            obj  = fact.object.strip()
            rel  = fact.relation.strip()

            if not subj or not obj or not rel:
                continue

            # --- Historical graph: keep everything ---
            for node in (subj, obj):
                if not self.graph.has_node(node):
                    self.graph.add_node(node, type="entity")
            self.graph.add_edge(subj, obj, relation=rel, step_id=self.current_step)

            # --- State graph: smart update ---
            self._update_state_graph(subj, obj, rel)

        if self.current_step % 50 == 0:
            self._archive_old_edges()

    def add_event(self, event: EventNode) -> None:
        """Register a major event node in the historical graph."""
        self.events.append(event)
        node_id = event.event_id
        self.graph.add_node(node_id, type="event", description=event.description,
                            step_id=event.step_id, location=event.location)
        for participant in event.participants:
            if not self.graph.has_node(participant):
                self.graph.add_node(participant, type="entity")
            self.graph.add_edge(participant, node_id, relation="participatedIn",
                                step_id=event.step_id)
        if event.location:
            if not self.graph.has_node(event.location):
                self.graph.add_node(event.location, type="location")
            self.graph.add_edge(node_id, event.location, relation="occurredAt",
                                step_id=event.step_id)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_all_facts_strings(self) -> List[str]:
        return [
            f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]"
            for u, v, data in self.graph.edges(data=True)
        ]

    def get_recent_facts_strings(self, n: int = 20) -> List[str]:
        edges = sorted(
            self.graph.edges(data=True),
            key=lambda e: e[2].get("step_id", 0),
            reverse=True,
        )
        return [
            f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]"
            for u, v, data in edges[:n]
        ]

    def get_relevant_facts(self, query_entities: List[str], depth: int = 2) -> List[str]:
        """Multi-hop BFS retrieval from the historical graph."""
        relevant_edges: Set[Tuple] = set()
        visited: Set[str] = set()

        query_lower = {e.lower() for e in query_entities}
        start_nodes = [n for n in self.graph.nodes() if str(n).lower() in query_lower]

        frontier: deque = deque()
        for node in start_nodes:
            frontier.append((node, 0))

        while frontier:
            node, hop = frontier.popleft()
            if node in visited or hop > depth:
                continue
            visited.add(node)

            for u, v, k, data in self.graph.out_edges(node, data=True, keys=True):
                relevant_edges.add((u, v, data["relation"], data.get("step_id", 0)))
                if hop + 1 <= depth:
                    frontier.append((v, hop + 1))

            for u, v, k, data in self.graph.in_edges(node, data=True, keys=True):
                relevant_edges.add((u, v, data["relation"], data.get("step_id", 0)))
                if hop + 1 <= depth:
                    frontier.append((u, hop + 1))

        for node in start_nodes:
            if self.archive_graph.has_node(node):
                for u, v, k, data in self.archive_graph.out_edges(node, data=True, keys=True):
                    relevant_edges.add((u, v, data["relation"], data.get("step_id", 0)))

        return [
            f"({u}, {rel}, {v}) [Step: {step}]"
            for u, v, rel, step in sorted(relevant_edges, key=lambda x: x[3], reverse=True)
        ]

    def get_character_context(self, character: str) -> List[str]:
        return self.get_relevant_facts([character], depth=2)

    def get_event_context(self, event_id: str) -> List[str]:
        if not self.graph.has_node(event_id):
            return []
        facts = []
        for u, v, data in self.graph.out_edges(event_id, data=True):
            facts.append(f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]")
        for u, v, data in self.graph.in_edges(event_id, data=True):
            facts.append(f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]")
        return facts

    def get_latest_state(self, subject: str, relation: str) -> Optional[str]:
        """Return most recent object value for (subject, relation) from historical graph."""
        best_val: Optional[str] = None
        best_step: int = -1
        subject_l = subject.lower()
        relation_l = relation.lower()

        for node in self.graph.nodes():
            if str(node).lower() != subject_l:
                continue
            for _, v, data in self.graph.out_edges(node, data=True):
                if data.get("relation", "").lower() == relation_l:
                    s = data.get("step_id", 0)
                    if s > best_step:
                        best_step = s
                        best_val = v
        return best_val

    def get_node_attributes(self, node: str) -> Dict:
        """Return scalar attribute dict for a node in the state graph."""
        if self.state_graph.has_node(node):
            return dict(self.state_graph.nodes[node])
        return {}

    def get_graph_stats(self) -> Dict:
        return {
            "historical_nodes": self.graph.number_of_nodes(),
            "historical_edges": self.graph.number_of_edges(),
            "state_nodes": self.state_graph.number_of_nodes(),
            "state_edges": self.state_graph.number_of_edges(),
            "archived_edges": self.archive_graph.number_of_edges(),
            "events": len(self.events),
            "current_step": self.current_step,
        }

    def compute_kgcs(self) -> float:
        """
        KG Consistency Score — measures how contradiction-free the historical graph is.

        For each (subject, scalar_relation) pair, walk values in step order.
        A contradiction is an impossible reversal:
          - isAlive: false -> true with no resurrection edge in between
          - Any other scalar: same subject+relation has two different values at the SAME step

        Returns a score from 0.0 to 100.0 (higher = more consistent).
        """
        _SCALAR = {"isalive", "locatedin", "locatedat", "health", "feels", "faction", "emotional_state"}

        # Group (subject, relation) -> list of (step_id, object) sorted by step
        timeline: Dict[Tuple, list] = {}
        for u, v, data in self.graph.edges(data=True):
            rel = data.get("relation", "").lower()
            if rel not in _SCALAR:
                continue
            key = (str(u).lower(), rel)
            timeline.setdefault(key, []).append((data.get("step_id", 0), str(v).lower()))

        total = 0
        contradictions = 0

        for (subj, rel), entries in timeline.items():
            entries.sort(key=lambda x: x[0])
            total += len(entries)

            if rel == "isalive":
                # Detect dead->alive reversal without resurrection
                dead_at: Optional[int] = None
                for step, val in entries:
                    if val in {"false", "no", "dead", "0"}:
                        dead_at = step
                    elif val in {"true", "yes", "alive", "1"} and dead_at is not None:
                        # Check if a resurrection edge exists between dead_at and this step
                        has_resurrection = any(
                            data.get("relation", "").lower() in {"resurrectedby", "revivedby"}
                            and dead_at <= data.get("step_id", 0) <= step
                            for _, __, data in self.graph.out_edges(subj, data=True)
                        )
                        if not has_resurrection:
                            contradictions += 1
                        dead_at = None  # reset after resurrection accounted for
            else:
                # Detect same-step conflicts (two different values at the exact same step)
                by_step: Dict[int, set] = {}
                for step, val in entries:
                    by_step.setdefault(step, set()).add(val)
                for step, vals in by_step.items():
                    if len(vals) > 1:
                        contradictions += 1

        if total == 0:
            return 100.0
        return round(max(0.0, 100.0 * (1 - contradictions / total)), 1)

    # ------------------------------------------------------------------
    # State-graph management
    # ------------------------------------------------------------------

    def _update_state_graph(self, subject: str, obj: str, relation: str) -> None:
        """
        Whitelist-based state graph update.

        ONLY relations in _ENTITY_RELATIONS create graph edges.
        EVERYTHING ELSE is stored as a node attribute on the subject.
        This prevents any scalar value, adjective, emotion, or goal phrase
        from becoming a visible node in the graph.
        """
        rel_lower = relation.lower()

        # Ensure subject node exists in state graph
        if not self.state_graph.has_node(subject):
            self.state_graph.add_node(subject, type="entity")

        # Case 1: NOT an entity relation → store as node attribute, never create an edge
        if rel_lower not in _ENTITY_RELATIONS:
            self.state_graph.nodes[subject][rel_lower] = obj
            return

        # Case 2: Entity relation, but object looks like a value → store as attribute
        if self._is_value_node(obj):
            self.state_graph.nodes[subject][rel_lower] = obj
            return

        # Case 3: Genuine entity-to-entity edge
        if not self.state_graph.has_node(obj):
            self.state_graph.add_node(obj, type="entity")

        # For location relations, remove old location edge first (one location at a time)
        if rel_lower in {"locatedin", "locatedat", "isin", "movesto"}:
            old_edges = [
                (u, v) for u, v, data in self.state_graph.out_edges(subject, data=True)
                if data.get("relation", "").lower() in {"locatedin", "locatedat", "isin", "movesto"}
            ]
            self.state_graph.remove_edges_from(old_edges)

        self.state_graph.add_edge(subject, obj, relation=relation,
                                  step_id=self.current_step)

    def _is_value_node(self, name: str) -> bool:
        """True if this string looks like a scalar value, not a real entity."""
        if name.lower() in _VALUE_WORDS:
            return True
        if len(name) > _MAX_LABEL_LEN:
            return True
        # Looks like a full sentence (contains multiple spaces and lowercase start)
        if name.count(" ") > 4 and name[0].islower():
            return True
        return False

    # ------------------------------------------------------------------
    # Archiving
    # ------------------------------------------------------------------

    def _archive_old_edges(self) -> None:
        threshold = self.current_step - self.archive_horizon
        if threshold <= 0:
            return
        edges_to_archive = [
            (u, v, k, data)
            for u, v, k, data in self.graph.edges(data=True, keys=True)
            if data.get("step_id", 0) < threshold
        ]
        for u, v, k, data in edges_to_archive:
            if not self.archive_graph.has_node(u):
                self.archive_graph.add_node(u, **self.graph.nodes[u])
            if not self.archive_graph.has_node(v):
                self.archive_graph.add_node(v, **self.graph.nodes[v])
            self.archive_graph.add_edge(u, v, **data)
            self.graph.remove_edge(u, v, k)
        logger.debug("Archived %d old edges", len(edges_to_archive))

    def rebuild_state_graph_from_scratch(self) -> None:
        self.state_graph = nx.DiGraph()
        seen: Dict[Tuple, Tuple] = {}
        for u, v, data in sorted(
            self.graph.edges(data=True), key=lambda e: e[2].get("step_id", 0)
        ):
            key = (str(u).lower(), data.get("relation", "").lower())
            seen[key] = (u, v, data)
        for (_, _), (u, v, data) in seen.items():
            self._update_state_graph(u, v, data.get("relation", ""))
