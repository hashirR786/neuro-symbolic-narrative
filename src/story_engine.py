"""
StoryEngine — orchestrates the three-phase Neuro-Symbolic RAG pipeline.

Phase 1 : Hybrid Retrieval  (FAISS + KG + WorldState)
Phase 2 : LLM Story Generation
Phase 3 : Neuro-Symbolic Verification → Self-Correction loop

Enhancements over the original:
  * WorldStateManager kept in sync after every verified step.
  * World-state context + hard generation constraints injected into every prompt.
  * Richer correction instruction that names the exact violated rules.
  * Detailed violation log stored on the engine for dashboard display.
"""

import logging
from typing import Any, Dict, List, Optional

from src.hybrid_retriever import HybridRetriever
from src.kg_manager import KGManager
from src.llm_manager import LLMManager
from src.schema import ViolationReport
from src.verifier import ConsistencyVerifier
from src.world_state import WorldStateManager

logger = logging.getLogger(__name__)


class StoryEngine:
    """Orchestrates the Neuro-Symbolic RAG pipeline with self-correction."""

    def __init__(self, use_neurosymbolic: bool = True) -> None:
        self.kg = KGManager()
        self.world_state = WorldStateManager()
        self.llm = LLMManager()
        self.retriever = HybridRetriever(self.kg, world_state=self.world_state)
        self.verifier = ConsistencyVerifier(self.kg, world_state=self.world_state)

        self.use_neurosymbolic = use_neurosymbolic
        self.max_retries = 3

        # Telemetry — persisted across steps for dashboard display
        self.violation_log: List[Dict[str, Any]] = []
        self.last_violations: List[ViolationReport] = []
        self.total_corrections: int = 0
        self.total_steps: int = 0
        self.consistent_steps: int = 0

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def generate_step(self, user_input: str) -> Dict[str, Any]:
        """
        Generate the next story beat, verify it, and commit to the knowledge base.

        Returns a dict with keys:
          text              : str
          facts             : list[dict]
          corrections_made  : int
          is_consistent     : bool
          violations        : list[dict]   (new — structured violation reports)
        """
        self.total_steps += 1

        # Phase 1 — Retrieval
        if self.use_neurosymbolic:
            context = self.retriever.retrieve(user_input)
        else:
            context = "Prior context not available in baseline mode."

        story_text = ""
        final_facts = []
        is_consistent = True
        correction_attempts = 0
        last_violations: List[ViolationReport] = []

        for attempt in range(self.max_retries):
            # Build correction instruction for retries
            instruction = ""
            if attempt > 0 and last_violations:
                rules_broken = "; ".join(
                    f"[{v.rule}] {v.description}" for v in last_violations
                    if v.severity == "error"
                )
                instruction = (
                    f"CRITICAL REWRITE REQUIRED.\n"
                    f"Your previous response contained {len(last_violations)} logical violation(s):\n"
                    f"{rules_broken}\n"
                    f"Rewrite the story segment so that NONE of these violations occur."
                )

            # Phase 2 — Generation
            story_text = self.llm.generate_story(user_input, context, instruction=instruction)

            if not self.use_neurosymbolic:
                break

            # Phase 3a — Fact extraction
            facts = self.llm.extract_facts(story_text)
            step_id = self.kg.current_step + 1
            for f in facts:
                f.step_id = step_id

            # Phase 3b — Verification
            last_violations = self.verifier.get_violations(facts)
            errors = [v for v in last_violations if v.severity == "error"]

            if not errors:
                final_facts = facts
                is_consistent = True
                break
            else:
                correction_attempts += 1
                is_consistent = False
                logger.warning(
                    "Step %d attempt %d: %d error(s) — %s",
                    self.total_steps, attempt + 1, len(errors),
                    [v.rule for v in errors],
                )

        # If all retries exhausted, commit the last attempt anyway
        if self.use_neurosymbolic and not final_facts:
            final_facts = self.llm.extract_facts(story_text)

        # Phase 4 — Commit to knowledge bases
        if self.use_neurosymbolic:
            self.kg.add_facts(final_facts)
            self.world_state.update_from_facts(final_facts)
            self.retriever.add_text(story_text)

            if not is_consistent:
                story_text += (
                    f"\n\n[System Warning: Narrative inconsistency remains after "
                    f"{self.max_retries} rewrite attempts → "
                    + "; ".join(v.rule for v in last_violations if v.severity == "error")
                    + "]"
                )

        # Telemetry
        self.total_corrections += correction_attempts
        if is_consistent:
            self.consistent_steps += 1
        self.last_violations = last_violations
        if last_violations:
            self.violation_log.append({
                "step": self.total_steps,
                "violations": [v.model_dump() for v in last_violations],
                "corrections": correction_attempts,
            })

        return {
            "text": story_text,
            "facts": [f.model_dump() for f in final_facts],
            "corrections_made": correction_attempts,
            "is_consistent": is_consistent,
            "violations": [v.model_dump() for v in last_violations],
        }

    # ------------------------------------------------------------------
    # Convenience getters for the dashboard
    # ------------------------------------------------------------------

    def get_consistency_rate(self) -> float:
        if self.total_steps == 0:
            return 1.0
        return self.consistent_steps / self.total_steps

    def get_session_stats(self) -> Dict[str, Any]:
        kg_stats = self.kg.get_graph_stats()
        ws = self.world_state
        return {
            "total_steps": self.total_steps,
            "consistent_steps": self.consistent_steps,
            "consistency_rate": self.get_consistency_rate(),
            "total_corrections": self.total_corrections,
            "characters": len(ws.characters),
            "dead_characters": len(ws.get_dead_characters()),
            "items": len(ws.items),
            "locations": len(ws.locations),
            "events": len(ws.events),
            **kg_stats,
        }
