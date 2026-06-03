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

# Relations whose object is a scalar VALUE — stored as node attribute, not a graph edge
_SCALAR_RELATIONS: frozenset = frozenset({
    "isalive", "alive", "isdead",
    "health", "wounded", "injured", "healed",
    "feels", "emotional_state", "mood",
    "faction",
    "goal", "wantsto", "seeks",
    "isworried", "isworriedabo", "isworrriedabout",
})

# Relations whose object is a real ENTITY — kept as edges in the state graph
_ENTITY_RELATIONS: frozenset = frozenset({
    "locatedin", "locatedat", "isin", "presentat", "movesto", "travels",
    "hasitem", "owns", "carries", "pickedup", "holds", "dropped", "gave",
    "friendof", "enemyof", "alliedwith", "partnerof", "marriedto",
    "rivalof", "servantof", "masterof",
    "attacks", "kills", "rescues", "speaks", "commands",
    "participatedin", "occurredat", "causes",
})

# Maximum character length for a node label to be shown in the state graph
_MAX_LABEL_LEN: int = 30

# Values that look like scalar words, not entity names — filtered from state graph nodes
_VALUE_WORDS: frozenset = frozenset({
    "true", "false", "yes", "no", "dead", "alive",
    "unknown", "none", "null", "0", "1",
})


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

    # ------------------------------------------------------------------
    # State-graph management
    # ------------------------------------------------------------------

    def _update_state_graph(self, subject: str, obj: str, relation: str) -> None:
        """
        Smart state graph update:
        - Scalar relations → stored as node attributes on subject (no edge, no value node)
        - Entity relations → stored as edges between entity nodes
        - Long strings or value words → dropped from state graph entirely
        """
        rel_lower = relation.lower()

        # Ensure subject node exists in state graph
        if not self.state_graph.has_node(subject):
            self.state_graph.add_node(subject, type="entity")

        # Case 1: Scalar relation → store as node attribute
        if rel_lower in _SCALAR_RELATIONS:
            self.state_graph.nodes[subject][rel_lower] = obj
            return

        # Case 2: Object is a value word or too long → skip
        if self._is_value_node(obj):
            # Still store as attribute if it looks scalar
            self.state_graph.nodes[subject][rel_lower] = obj
            return

        # Case 3: Entity relation → add as edge
        if not self.state_graph.has_node(obj):
            self.state_graph.add_node(obj, type="entity")

        # For state-type relations, remove old edge with same relation first
        if rel_lower in {"locatedin", "locatedat", "isin", "movesto"}:
            old_edges = [
                (u, v) for u, v, data in self.state_graph.out_edges(subject, data=True)
                if data.get("relation", "").lower() == rel_lower
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
