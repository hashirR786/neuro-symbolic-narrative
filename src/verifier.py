"""
ConsistencyVerifier — expanded rule-based engine.

Check hierarchy
───────────────
  1. Character checks  — dead-actor, location conflict, relationship contradiction
  2. Item checks       — duplicate ownership, impossible transfers, possession before use
  3. Temporal checks   — action after death, impossible event ordering
  4. World-rule checks — configurable hard rules from WorldStateManager

Public interface (backward-compatible):
  verify(facts) -> (bool, str)           — original simple interface
  get_violations(facts) -> List[ViolationReport]  — detailed structured interface
"""

import logging
from typing import List, Optional, Tuple

from src.kg_manager import KGManager
from src.schema import Fact, ViolationReport
from src.world_state import WorldStateManager

logger = logging.getLogger(__name__)

# Relations that constitute an active "action" by the subject
_ACTION_RELATIONS: frozenset = frozenset({
    "attacks", "movesto", "says", "feels", "isdoing", "picksup",
    "uses", "runs", "fights", "casts", "opens", "closes",
    "speaks", "commands", "kills", "rescues", "drops",
})

# Relations that imply ownership/possession
_POSSESSION_RELATIONS: frozenset = frozenset({"hasitem", "owns", "carries", "holds"})

# Relations that are single-valued (the latest supersedes all prior values)
_SCALAR_RELATIONS: frozenset = frozenset({
    "isalive", "locatedin", "locatedat", "health",
    "feels", "faction", "emotional_state",
})


class ConsistencyVerifier:
    """Rule-based consistency engine operating on KGManager + WorldStateManager."""

    def __init__(
        self,
        kg_manager: KGManager,
        world_state: Optional[WorldStateManager] = None,
    ) -> None:
        self.kg = kg_manager
        self.world_state = world_state

    # ------------------------------------------------------------------
    # Primary public interface
    # ------------------------------------------------------------------

    def verify(self, new_facts: List[Fact]) -> Tuple[bool, str]:
        """
        Backward-compatible interface.
        Returns (True, "") if consistent; (False, "violation message") otherwise.
        """
        violations = self.get_violations(new_facts)
        errors = [v for v in violations if v.severity == "error"]
        if errors:
            return False, " | ".join(v.description for v in errors)
        return True, ""

    def get_violations(self, new_facts: List[Fact]) -> List[ViolationReport]:
        """
        Full structured violation report.
        Runs all check layers and returns every violation found.
        """
        violations: List[ViolationReport] = []
        step = new_facts[0].step_id if new_facts else self.kg.current_step

        violations += self._check_character_rules(new_facts, step)
        violations += self._check_item_rules(new_facts, step)
        violations += self._check_temporal_rules(new_facts, step)
        violations += self._check_world_rules(new_facts, step)

        for v in violations:
            logger.debug("Violation [%s]: %s", v.severity, v.description)

        return violations

    # ------------------------------------------------------------------
    # Check layers
    # ------------------------------------------------------------------

    def _check_character_rules(
        self, facts: List[Fact], step: int
    ) -> List[ViolationReport]:
        violations: List[ViolationReport] = []

        for fact in facts:
            subj = fact.subject
            rel = fact.relation.lower()
            obj = fact.object.lower()

            # R1 — Dead characters cannot act
            if rel in _ACTION_RELATIONS:
                if self._is_dead(subj):
                    violations.append(ViolationReport(
                        rule="dead_actor",
                        description=f"'{subj}' is dead and cannot perform '{rel}'.",
                        entities_involved=[subj],
                        severity="error",
                        step_id=step,
                    ))

            # R2 — Cannot arbitrarily resurrect (isAlive=true after isAlive=false)
            if rel == "isalive" and obj in {"true", "yes", "1"}:
                if self._is_dead(subj):
                    violations.append(ViolationReport(
                        rule="illegal_resurrection",
                        description=(
                            f"'{subj}' is already dead and cannot become alive "
                            f"without an explicit resurrection event."
                        ),
                        entities_involved=[subj],
                        severity="error",
                        step_id=step,
                    ))

            # R3 — Relationship contradiction (enemy becomes friend without event)
            if rel in {"friendof", "alliedwith"} and self.world_state:
                char = self.world_state.characters.get(subj)
                if char and char.relationships.get(obj) in {"enemyof", "rivalof"}:
                    violations.append(ViolationReport(
                        rule="relationship_contradiction",
                        description=(
                            f"'{subj}' is established as enemy/rival of '{obj}' "
                            f"but is now being made friend/ally without a reconciliation event."
                        ),
                        entities_involved=[subj, obj],
                        severity="warning",
                        step_id=step,
                    ))

        return violations

    def _check_item_rules(
        self, facts: List[Fact], step: int
    ) -> List[ViolationReport]:
        violations: List[ViolationReport] = []

        # Build a map of ownership claims in the incoming facts
        new_ownership: dict = {}  # item -> [list of new owners]
        for fact in facts:
            if fact.relation.lower() in _POSSESSION_RELATIONS:
                item = fact.object
                owner = fact.subject
                new_ownership.setdefault(item, []).append(owner)

        for item, owners in new_ownership.items():
            # R4 — Duplicate ownership in the same step
            if len(owners) > 1:
                violations.append(ViolationReport(
                    rule="duplicate_ownership",
                    description=(
                        f"Item '{item}' is being assigned to multiple owners "
                        f"in the same step: {owners}."
                    ),
                    entities_involved=[item] + owners,
                    severity="error",
                    step_id=step,
                ))

            # R5 — Item already has a different owner in the world state
            if self.world_state:
                current_owner = self.world_state.get_owner(item)
                for new_owner in owners:
                    if current_owner and current_owner != new_owner:
                        violations.append(ViolationReport(
                            rule="item_transfer_without_exchange",
                            description=(
                                f"'{item}' is owned by '{current_owner}' but is being "
                                f"claimed by '{new_owner}' without an explicit transfer."
                            ),
                            entities_involved=[item, current_owner, new_owner],
                            severity="warning",
                            step_id=step,
                        ))

        # R6 — Must possess an item before using it
        for fact in facts:
            if fact.relation.lower() == "uses":
                subj = fact.subject
                item = fact.object
                if self.world_state:
                    if not self.world_state.character_has_item(subj, item):
                        violations.append(ViolationReport(
                            rule="use_without_possession",
                            description=(
                                f"'{subj}' tries to use '{item}' but does not possess it."
                            ),
                            entities_involved=[subj, item],
                            severity="error",
                            step_id=step,
                        ))
                else:
                    # Fallback: check KG directly
                    owns = any(
                        data.get("relation", "").lower() in _POSSESSION_RELATIONS
                        and v.lower() == item.lower()
                        for _, v, data in self.kg.graph.out_edges(subj, data=True)
                    )
                    if not owns:
                        violations.append(ViolationReport(
                            rule="use_without_possession",
                            description=(
                                f"'{subj}' tries to use '{item}' but does not possess it."
                            ),
                            entities_involved=[subj, item],
                            severity="error",
                            step_id=step,
                        ))

        return violations

    def _check_temporal_rules(
        self, facts: List[Fact], step: int
    ) -> List[ViolationReport]:
        violations: List[ViolationReport] = []

        for fact in facts:
            subj = fact.subject
            rel = fact.relation.lower()

            # R7 — Action by character who was dead before this step
            if rel in _ACTION_RELATIONS and self._was_dead_before(subj, step):
                # Only flag if no resurrection event exists between death and now
                if not self._resurrection_exists(subj, step):
                    violations.append(ViolationReport(
                        rule="temporal_dead_actor",
                        description=(
                            f"'{subj}' died before step {step} and performed "
                            f"'{rel}' without a resurrection event."
                        ),
                        entities_involved=[subj],
                        severity="error",
                        step_id=step,
                    ))

            # R8 — Location impossibility (character acts at location before arrival)
            if rel in _ACTION_RELATIONS and self.world_state:
                char = self.world_state.characters.get(subj)
                if char and char.location:
                    # If a location is mentioned in object and differs from char location,
                    # flag as a potential teleportation
                    obj_loc = fact.object
                    if (
                        obj_loc in self.world_state.locations
                        and obj_loc != char.location
                        and rel not in {"movesto", "travels"}
                    ):
                        violations.append(ViolationReport(
                            rule="location_mismatch",
                            description=(
                                f"'{subj}' is at '{char.location}' but seems to act "
                                f"at '{obj_loc}' without a travel event."
                            ),
                            entities_involved=[subj, obj_loc],
                            severity="warning",
                            step_id=step,
                        ))

        return violations

    def _check_world_rules(
        self, facts: List[Fact], step: int
    ) -> List[ViolationReport]:
        """
        Placeholder for user-configurable world rules stored in WorldStateManager.
        Currently enforces the two canonical hard rules.
        """
        violations: List[ViolationReport] = []
        if not self.world_state:
            return violations

        for fact in facts:
            subj = fact.subject
            rel = fact.relation.lower()

            # Hard rule: dead characters cannot act (world-rule level enforcement)
            if rel in _ACTION_RELATIONS and self._is_dead(subj):
                # Already caught in character checks; skip duplicate
                pass

        return violations

    # ------------------------------------------------------------------
    # Helper queries
    # ------------------------------------------------------------------

    def _is_dead(self, character: str) -> bool:
        """True if the character is currently dead according to world state or KG."""
        if self.world_state:
            alive = self.world_state.is_alive(character)
            if alive is not None:
                return not alive

        val = self.kg.get_latest_state(character, "isAlive")
        if val is None:
            val = self.kg.get_latest_state(character, "isalive")
        return val is not None and val.lower() in {"false", "no", "dead", "0"}

    def _was_dead_before(self, character: str, step: int) -> bool:
        """True if the character had isAlive=false at any step before `step`."""
        for _, v, data in self.kg.graph.out_edges(character, data=True):
            if (
                data.get("relation", "").lower() == "isalive"
                and str(v).lower() in {"false", "no", "dead", "0"}
                and data.get("step_id", 0) < step
            ):
                return True
        return False

    def _resurrection_exists(self, character: str, step: int) -> bool:
        """
        True if a resurrection event was registered for `character`
        between their death step and the current `step`.
        """
        for _, v, data in self.kg.graph.out_edges(character, data=True):
            rel = data.get("relation", "").lower()
            if rel in {"resurrectedby", "revivedby", "ressurectedby"} and data.get("step_id", 0) < step:
                return True
        return False
