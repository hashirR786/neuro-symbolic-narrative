"""
KGManager — NetworkX-based dual Knowledge Graph.

  historical_graph : MultiDiGraph  — every fact ever added, used for retrieval and reasoning.
  state_graph      : DiGraph        — only the latest valid state per entity, used for visualization.

Both graphs are kept in sync after every add_facts() call.
"""

import logging
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from src.schema import Fact, EventNode

logger = logging.getLogger(__name__)


class KGManager:
    """Manages the dual Knowledge Graph using NetworkX."""

    def __init__(self) -> None:
        # Historical graph: retains every fact across all time steps
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()

        # Current-state graph: pruned to the latest valid value per (subject, relation)
        # This is the default visualization target.
        self.state_graph: nx.DiGraph = nx.DiGraph()

        self.current_step: int = 0
        self.events: List[EventNode] = []

        # Archive: edges older than archive_horizon steps are moved here for scalability
        self.archive_graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self.archive_horizon: int = 200  # steps before archiving

    # ------------------------------------------------------------------
    # Core write API
    # ------------------------------------------------------------------

    def add_facts(self, facts: List[Fact]) -> None:
        """Add a list of facts, updating both historical and state graphs."""
        self.current_step += 1

        for fact in facts:
            fact.step_id = self.current_step
            subj = fact.subject.strip()
            obj = fact.object.strip()
            rel = fact.relation.strip()

            if not subj or not obj or not rel:
                continue

            # --- Historical graph ---
            for node in (subj, obj):
                if not self.graph.has_node(node):
                    self.graph.add_node(node, type="entity")
            self.graph.add_edge(subj, obj, relation=rel, step_id=self.current_step)

            # --- State graph (latest value per subject+relation) ---
            self._update_state_graph(subj, obj, rel)

        # Periodic archiving to keep the historical graph manageable
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
        if event.cause_event_id and self.graph.has_node(event.cause_event_id):
            self.graph.add_edge(event.cause_event_id, node_id, relation="causes",
                                step_id=event.step_id)

    # ------------------------------------------------------------------
    # Read API — all retrieval methods operate on the historical graph
    # ------------------------------------------------------------------

    def get_all_facts_strings(self) -> List[str]:
        """Return all historical facts as human-readable strings."""
        return [
            f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]"
            for u, v, data in self.graph.edges(data=True)
        ]

    def get_recent_facts_strings(self, n: int = 20) -> List[str]:
        """Return the n most recent facts."""
        edges = sorted(
            self.graph.edges(data=True),
            key=lambda e: e[2].get("step_id", 0),
            reverse=True,
        )
        return [
            f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]"
            for u, v, data in edges[:n]
        ]

    def get_relevant_facts(
        self, query_entities: List[str], depth: int = 2
    ) -> List[str]:
        """
        Multi-hop retrieval: BFS up to `depth` hops from each query entity.
        Returns facts from both the active historical graph and the archive.
        """
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

        # Also check archive for the same entities
        for node in start_nodes:
            if self.archive_graph.has_node(node):
                for u, v, k, data in self.archive_graph.out_edges(node, data=True, keys=True):
                    relevant_edges.add((u, v, data["relation"], data.get("step_id", 0)))

        results = [
            f"({u}, {rel}, {v}) [Step: {step}]"
            for u, v, rel, step in sorted(relevant_edges, key=lambda x: x[3], reverse=True)
        ]
        return results

    def get_character_context(self, character: str) -> List[str]:
        """
        Character-centric retrieval: return everything known about a character —
        state, inventory, goals, relationships, recent events.
        """
        return self.get_relevant_facts([character], depth=2)

    def get_event_context(self, event_id: str) -> List[str]:
        """
        Event-centric retrieval: return the event node and all related facts.
        """
        if not self.graph.has_node(event_id):
            return []
        facts = []
        for u, v, data in self.graph.out_edges(event_id, data=True):
            facts.append(f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]")
        for u, v, data in self.graph.in_edges(event_id, data=True):
            facts.append(f"({u}, {data['relation']}, {v}) [Step: {data.get('step_id', 0)}]")
        return facts

    def get_latest_state(self, subject: str, relation: str) -> Optional[str]:
        """
        Return the most recent object value for (subject, relation).
        Case-insensitive on both subject and relation.
        """
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

    def get_state_graph_edges(self) -> List[Tuple[str, str, str]]:
        """Return (subject, relation, object) triples from the current state graph."""
        return [
            (u, data.get("relation", ""), v)
            for u, v, data in self.state_graph.edges(data=True)
        ]

    def get_graph_stats(self) -> Dict[str, int]:
        """Return basic graph statistics."""
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
        Update the current-state graph so it always reflects the latest value
        for each (subject, relation) pair.  For state-type relations (isAlive,
        locatedIn, health, etc.) we remove the old edge before adding the new one.
        """
        state_relations = {
            "isalive", "locatedin", "locatedat", "health", "feels",
            "emotional_state", "faction",
        }
        for node in (subject, obj):
            if not self.state_graph.has_node(node):
                self.state_graph.add_node(node, type="entity")

        if relation.lower() in state_relations:
            # Remove any existing edge with the same relation label from subject
            edges_to_remove = [
                (u, v)
                for u, v, data in self.state_graph.out_edges(subject, data=True)
                if data.get("relation", "").lower() == relation.lower()
            ]
            self.state_graph.remove_edges_from(edges_to_remove)

        self.state_graph.add_edge(subject, obj, relation=relation,
                                  step_id=self.current_step)

    # ------------------------------------------------------------------
    # Archiving / scalability
    # ------------------------------------------------------------------

    def _archive_old_edges(self) -> None:
        """
        Move edges older than `archive_horizon` steps from the historical graph
        to the archive graph to keep active retrieval fast.
        """
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

        logger.debug("Archived %d edges older than step %d", len(edges_to_archive), threshold)

    def rebuild_state_graph_from_scratch(self) -> None:
        """
        Rebuild the state graph from the full historical graph.
        Useful after loading a session or after bulk fact imports.
        """
        self.state_graph = nx.DiGraph()
        seen: Dict[Tuple[str, str], Tuple[str, int]] = {}

        for u, v, data in sorted(
            self.graph.edges(data=True), key=lambda e: e[2].get("step_id", 0)
        ):
            key = (str(u).lower(), data.get("relation", "").lower())
            seen[key] = (v, data.get("step_id", 0))

        for (subj, rel), (obj, step) in seen.items():
            if not self.state_graph.has_node(subj):
                self.state_graph.add_node(subj)
            if not self.state_graph.has_node(obj):
                self.state_graph.add_node(obj)
            self.state_graph.add_edge(subj, obj, relation=rel, step_id=step)
