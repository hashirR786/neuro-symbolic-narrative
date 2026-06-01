"""
HybridRetriever — dense FAISS semantic search + symbolic KG retrieval.

Enhancements over the original:
  * Multi-hop KG retrieval (depth=2 by default).
  * Character-centric retrieval: dedicate a retrieval pass for named characters.
  * Event-centric retrieval: pull related historical events before generation.
  * World-state context injection: inject the live WorldStateManager snapshot.
"""

import logging
import re
from typing import List, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.kg_manager import KGManager
from src.world_state import WorldStateManager

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Manages dense semantic search (FAISS) and symbolic search (KG)."""

    def __init__(
        self,
        kg_manager: KGManager,
        world_state: Optional[WorldStateManager] = None,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.kg = kg_manager
        self.world_state = world_state
        self.embedding_model = SentenceTransformer(model_name)
        # API was renamed in newer sentence-transformers versions
        _dim_fn = getattr(
            self.embedding_model,
            "get_embedding_dimension",
            None,
        ) or getattr(self.embedding_model, "get_sentence_embedding_dimension", None)
        dim = _dim_fn()
        self.index = faiss.IndexFlatL2(dim)
        self.documents: List[str] = []

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def add_text(self, text: str) -> None:
        """Index a story segment into FAISS."""
        if not text.strip():
            return
        self.documents.append(text)
        vec = self.embedding_model.encode([text])
        self.index.add(np.array(vec, dtype="float32"))

    # ------------------------------------------------------------------
    # Retrieval API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        extracted_entities: Optional[List[str]] = None,
        top_k: int = 3,
    ) -> str:
        """
        Returns a rich context string composed of:
          1. Semantic recall (FAISS) — most relevant past story segments.
          2. Symbolic recall (KG multi-hop) — facts about named entities.
          3. Character-centric recall — latest state for every named character
             mentioned in the query.
          4. World-state snapshot — current state from WorldStateManager.
          5. Generation constraints — hard rules derived from world state.
        """
        parts: List[str] = []

        # 1. Semantic recall
        semantic = self._semantic_recall(query, top_k)
        parts.append("=== RECENT & RELEVANT STORY SEGMENTS ===\n" + semantic)

        # 2. Symbolic multi-hop recall
        entities = extracted_entities or self._extract_entities_heuristic(query)
        symbolic = self._symbolic_recall(entities)
        parts.append("=== RELEVANT WORLD FACTS (KNOWLEDGE GRAPH) ===\n" + symbolic)

        # 3. Character-centric recall (dedicated pass per character in query)
        char_ctx = self._character_recall(entities)
        if char_ctx:
            parts.append("=== CHARACTER STATE (KNOWLEDGE GRAPH) ===\n" + char_ctx)

        # 4. World-state snapshot
        if self.world_state:
            parts.append(self.world_state.get_world_context_for_prompt())

        # 5. Generation constraints
        if self.world_state:
            parts.append(self.world_state.get_generation_constraints())

        return "\n\n".join(parts)

    def retrieve_character(self, character: str) -> str:
        """Return a full character dossier for a single named character."""
        kg_facts = "\n".join(self.kg.get_character_context(character))
        ws_ctx = (
            self.world_state.get_character_context(character) if self.world_state else ""
        )
        return f"=== {character.upper()} — KG FACTS ===\n{kg_facts}\n\n{ws_ctx}"

    def retrieve_event(self, event_id: str) -> str:
        """Return all facts related to a specific event node."""
        facts = "\n".join(self.kg.get_event_context(event_id))
        return f"=== EVENT: {event_id} ===\n{facts}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _semantic_recall(self, query: str, top_k: int) -> str:
        if not self.documents:
            return "No prior story segments."
        vec = self.embedding_model.encode([query])
        k = min(top_k, len(self.documents))
        _, indices = self.index.search(np.array(vec, dtype="float32"), k)
        docs = [self.documents[i] for i in indices[0] if 0 <= i < len(self.documents)]
        return "\n---\n".join(docs) if docs else "No relevant segments found."

    def _symbolic_recall(self, entities: List[str]) -> str:
        if entities:
            facts = self.kg.get_relevant_facts(entities, depth=2)
        else:
            facts = self.kg.get_recent_facts_strings(15)
        return "\n".join(facts) if facts else "No established facts yet."

    def _character_recall(self, entities: List[str]) -> str:
        """
        For each entity that is a known character in the world state,
        return their dedicated context block.
        """
        if not self.world_state or not entities:
            return ""
        blocks: List[str] = []
        known = self.world_state.get_all_character_names()
        known_lower = {n.lower(): n for n in known}
        for ent in entities:
            canonical = known_lower.get(ent.lower())
            if canonical:
                blocks.append(self.world_state.get_character_context(canonical))
        return "\n\n".join(blocks)

    def _extract_entities_heuristic(self, text: str) -> List[str]:
        """
        Heuristic entity extraction: capitalised words that are not
        sentence-starters and known KG nodes.
        """
        # Simple: grab all capitalised tokens
        tokens = re.findall(r"\b[A-Z][a-z]+\b", text)
        # Intersect with known KG nodes for precision
        known = {str(n).lower() for n in self.kg.graph.nodes()}
        candidates = [t for t in tokens if t.lower() in known]
        return list(dict.fromkeys(candidates)) or tokens[:5]
