from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Fact(BaseModel):
    subject: str = Field(description="The entity or character (e.g., 'Hero')")
    relation: str = Field(description="The relationship or state (e.g., 'isAlive', 'locatedIn', 'hasItem')")
    object: str = Field(description="The target entity, state, or object (e.g., 'true', 'Castle', 'Sword')")
    step_id: int = Field(default=0, description="The sequence step in which this fact was established")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence (0–1)")


class FactExtraction(BaseModel):
    facts: List[Fact]


class CharacterState(BaseModel):
    name: str
    is_alive: bool = True
    location: Optional[str] = None
    health: str = "healthy"
    emotional_state: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    faction: Optional[str] = None
    inventory: List[str] = Field(default_factory=list)
    # key = other character name, value = relation type (e.g. "friendOf")
    relationships: Dict[str, str] = Field(default_factory=dict)
    last_updated_step: int = 0


class ItemState(BaseModel):
    name: str
    owner: Optional[str] = None
    location: Optional[str] = None
    last_updated_step: int = 0


class EventNode(BaseModel):
    event_id: str
    description: str
    participants: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    step_id: int = 0
    consequences: List[str] = Field(default_factory=list)
    cause_event_id: Optional[str] = None  # causal chain linkage


class ViolationReport(BaseModel):
    rule: str
    description: str
    entities_involved: List[str] = Field(default_factory=list)
    severity: str = "error"   # "error" | "warning"
    step_id: int = 0
