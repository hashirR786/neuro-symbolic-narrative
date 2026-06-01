"""
WorldStateManager — maintains a live, structured snapshot of all characters, items,
locations, and events.  It is updated after each verified story step and is the
authoritative source of truth that feeds both the verifier and the prompt builder.
"""

import logging
from typing import Dict, List, Optional, Any

from src.schema import CharacterState, ItemState, EventNode, Fact

logger = logging.getLogger(__name__)

# Relations that target a character and update its scalar fields
_ALIVE_RELATIONS = {"isalive", "alive", "isdead"}
_LOCATION_RELATIONS = {"locatedin", "locatedat", "isin", "presentat"}
_HEALTH_RELATIONS = {"health", "injured", "wounded", "healed"}
_EMOTION_RELATIONS = {"feels", "emotional_state", "mood"}
_FACTION_RELATIONS = {"faction", "memberof", "belongsto"}
_INVENTORY_RELATIONS = {"hasitem", "owns", "carries", "pickedup", "holds"}
_GOAL_RELATIONS = {"goal", "wantsto", "seeks"}
_RELATIONSHIP_RELATIONS = {
    "friendof", "enemyof", "alliedwith", "partnerof",
    "marriedto", "rivalof", "servantof", "masterof",
}
_DROP_RELATIONS = {"dropped", "lost", "gave", "transfers"}

DEFAULT_WORLD_RULES: List[str] = [
    "Dead characters cannot perform any actions.",
    "A character can only be in one location at a time.",
    "An item can only have one owner at a time.",
    "Characters cannot use items they do not possess.",
    "Events must respect strict temporal ordering.",
    "Magic cannot revive dead characters unless a resurrection event is declared.",
    "Locations must be reachable from the current position (no teleportation).",
]


class WorldStateManager:
    """
    Maintains a structured in-memory world state that stays synchronised with the
    KnowledgeGraph after every verified story step.
    """

    def __init__(self, world_rules: Optional[List[str]] = None) -> None:
        self.characters: Dict[str, CharacterState] = {}
        self.items: Dict[str, ItemState] = {}
        self.locations: List[str] = []
        self.events: List[EventNode] = []
        self.active_quests: List[str] = []
        self.timeline: List[Dict[str, Any]] = []
        self.world_rules: List[str] = world_rules if world_rules else DEFAULT_WORLD_RULES
        self.current_step: int = 0
        self._event_counter: int = 0

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update_from_facts(self, facts: List[Fact]) -> None:
        """Apply a batch of verified facts to the world state."""
        if not facts:
            return
        step = facts[0].step_id or self.current_step + 1
        self.current_step = step

        for fact in facts:
            subj = fact.subject.strip()
            rel = fact.relation.strip().lower()
            obj = fact.object.strip()
            if not subj or not rel or not obj:
                continue
            try:
                self._apply_fact(subj, rel, obj, step)
            except Exception as exc:
                logger.warning("WorldState apply_fact error: %s", exc)

        self.timeline.append({"step": step, "facts_applied": len(facts)})

    def register_event(
        self,
        description: str,
        participants: List[str],
        location: Optional[str],
        step: int,
        consequences: Optional[List[str]] = None,
        cause_event_id: Optional[str] = None,
    ) -> EventNode:
        """Explicitly register a major story event node."""
        self._event_counter += 1
        event = EventNode(
            event_id=f"Event_{self._event_counter}",
            description=description,
            participants=participants,
            location=location,
            step_id=step,
            consequences=consequences or [],
            cause_event_id=cause_event_id,
        )
        self.events.append(event)
        return event

    # ------------------------------------------------------------------
    # Context builders for LLM prompt injection
    # ------------------------------------------------------------------

    def get_world_context_for_prompt(self) -> str:
        """Returns a concise world-state block suitable for injection into a prompt."""
        lines: List[str] = ["=== CURRENT WORLD STATE ==="]

        if self.characters:
            lines.append("\nCharacters:")
            for name, char in self.characters.items():
                status = "alive" if char.is_alive else "DEAD"
                loc = char.location or "unknown location"
                lines.append(f"  - {name}: {status}, at {loc}, health={char.health}")
                if char.inventory:
                    lines.append(f"    inventory: {', '.join(char.inventory)}")
                if char.relationships:
                    rels = ", ".join(f"{o}({r})" for o, r in char.relationships.items())
                    lines.append(f"    relationships: {rels}")
                if char.goals:
                    lines.append(f"    goals: {', '.join(char.goals)}")
                if char.faction:
                    lines.append(f"    faction: {char.faction}")

        if self.items:
            lines.append("\nItems:")
            for item_name, item in self.items.items():
                owner = f"owned by {item.owner}" if item.owner else "unowned"
                loc = f"at {item.location}" if item.location else ""
                lines.append(f"  - {item_name}: {owner} {loc}".rstrip())

        if self.active_quests:
            lines.append(f"\nActive Quests: {', '.join(self.active_quests)}")

        lines.append("\nWorld Rules (must never be violated):")
        for rule in self.world_rules:
            lines.append(f"  * {rule}")

        return "\n".join(lines)

    def get_generation_constraints(self) -> str:
        """Returns hard generation constraints derived from the current world state."""
        lines: List[str] = ["=== GENERATION CONSTRAINTS (MUST OBEY) ==="]

        dead = [n for n, c in self.characters.items() if not c.is_alive]
        if dead:
            lines.append(
                f"DEAD characters — must NOT act, speak, move, or be revived without a resurrection event: "
                f"{', '.join(dead)}"
            )

        for name, char in self.characters.items():
            if char.is_alive and char.location:
                lines.append(
                    f"{name} is currently at '{char.location}' — a travel event is required to change location."
                )

        for item_name, item in self.items.items():
            if item.owner:
                lines.append(f"'{item_name}' is owned by {item.owner} — cannot be used or transferred without an exchange.")

        lines += [
            "Do NOT teleport characters or items without an explicit travel/transfer event.",
            "Do NOT introduce new characters without a proper introduction.",
            "Do NOT contradict previously established facts.",
            "Respect all established faction and relationship dynamics.",
            "Maintain strict temporal ordering of all events.",
        ]
        return "\n".join(lines)

    def get_character_context(self, name: str) -> str:
        """Returns a detailed context block for a single character."""
        if name not in self.characters:
            return f"No information available for '{name}'."
        char = self.characters[name]
        lines = [
            f"Character: {name}",
            f"  Alive: {char.is_alive}",
            f"  Location: {char.location or 'unknown'}",
            f"  Health: {char.health}",
            f"  Emotional State: {char.emotional_state or 'unknown'}",
            f"  Faction: {char.faction or 'none'}",
            f"  Inventory: {', '.join(char.inventory) if char.inventory else 'empty'}",
            f"  Goals: {', '.join(char.goals) if char.goals else 'none'}",
        ]
        if char.relationships:
            rels = ", ".join(f"{o} ({r})" for o, r in char.relationships.items())
            lines.append(f"  Relationships: {rels}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_alive(self, character: str) -> Optional[bool]:
        char = self.characters.get(character)
        return char.is_alive if char else None

    def get_location(self, character: str) -> Optional[str]:
        char = self.characters.get(character)
        return char.location if char else None

    def get_owner(self, item: str) -> Optional[str]:
        it = self.items.get(item)
        return it.owner if it else None

    def character_has_item(self, character: str, item: str) -> bool:
        char = self.characters.get(character)
        return item in char.inventory if char else False

    def get_all_character_names(self) -> List[str]:
        return list(self.characters.keys())

    def get_dead_characters(self) -> List[str]:
        return [n for n, c in self.characters.items() if not c.is_alive]

    def snapshot(self) -> Dict[str, Any]:
        """Returns a serialisable dict of the current world state."""
        return {
            "current_step": self.current_step,
            "characters": {n: c.model_dump() for n, c in self.characters.items()},
            "items": {n: i.model_dump() for n, i in self.items.items()},
            "locations": self.locations,
            "events": [e.model_dump() for e in self.events],
            "active_quests": self.active_quests,
            "timeline": self.timeline,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_fact(self, subject: str, relation: str, obj: str, step: int) -> None:
        """Route a single normalised fact to the correct state update method."""
        if relation in _ALIVE_RELATIONS:
            char = self._get_or_create_character(subject, step)
            if relation == "isdead":
                char.is_alive = False
            else:
                char.is_alive = obj.lower() not in {"false", "no", "dead", "0"}
            char.last_updated_step = step

        elif relation in _LOCATION_RELATIONS:
            # Could be a character or an item
            if subject in self.items:
                self.items[subject].location = obj
                self.items[subject].last_updated_step = step
            else:
                char = self._get_or_create_character(subject, step)
                char.location = obj
                char.last_updated_step = step
            if obj not in self.locations:
                self.locations.append(obj)

        elif relation in _HEALTH_RELATIONS:
            char = self._get_or_create_character(subject, step)
            char.health = obj
            char.last_updated_step = step

        elif relation in _EMOTION_RELATIONS:
            char = self._get_or_create_character(subject, step)
            char.emotional_state = obj
            char.last_updated_step = step

        elif relation in _FACTION_RELATIONS:
            char = self._get_or_create_character(subject, step)
            char.faction = obj
            char.last_updated_step = step

        elif relation in _INVENTORY_RELATIONS:
            char = self._get_or_create_character(subject, step)
            if obj not in char.inventory:
                char.inventory.append(obj)
            char.last_updated_step = step
            # Update item ownership
            self._get_or_create_item(obj, owner=subject, step=step)

        elif relation in _DROP_RELATIONS:
            # subject drops/transfers obj → remove from their inventory
            char = self.characters.get(subject)
            if char and obj in char.inventory:
                char.inventory.remove(obj)
                char.last_updated_step = step
            item = self.items.get(obj)
            if item and item.owner == subject:
                item.owner = None
                item.last_updated_step = step

        elif relation in _GOAL_RELATIONS:
            char = self._get_or_create_character(subject, step)
            if obj not in char.goals:
                char.goals.append(obj)
            char.last_updated_step = step

        elif relation in _RELATIONSHIP_RELATIONS:
            char = self._get_or_create_character(subject, step)
            char.relationships[obj] = relation
            char.last_updated_step = step
            # Mirror symmetric relations
            if relation in {"friendof", "alliedwith", "marriedto", "partnerof"}:
                other = self._get_or_create_character(obj, step)
                other.relationships[subject] = relation
                other.last_updated_step = step

        elif relation == "quest":
            if obj not in self.active_quests:
                self.active_quests.append(obj)

    def _get_or_create_character(self, name: str, step: int) -> CharacterState:
        if name not in self.characters:
            self.characters[name] = CharacterState(name=name, last_updated_step=step)
        return self.characters[name]

    def _get_or_create_item(
        self, name: str, owner: Optional[str] = None, step: int = 0
    ) -> ItemState:
        if name not in self.items:
            self.items[name] = ItemState(name=name, owner=owner, last_updated_step=step)
        else:
            if owner:
                self.items[name].owner = owner
            self.items[name].last_updated_step = step
        return self.items[name]
