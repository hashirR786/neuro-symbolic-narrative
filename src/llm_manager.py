"""
LLMManager — Ollama-backed generation and structured fact extraction.

Enhancements:
  * Richer fact-extraction prompt that captures character state, inventory,
    location, relationships, and major events.
  * Extraction prompt explicitly requests the full canonical relation vocabulary
    used by WorldStateManager and the verifier.
  * JSON parsing is more robust (handles both bare-list and wrapped-object responses).
"""

"""
LLMManager — supports both local Ollama and cloud providers (Groq, OpenAI, etc.)
via environment variables.  The OpenAI-compatible client is used for all backends.

Environment variables
─────────────────────
  LLM_PROVIDER   : "ollama" (default) | "groq" | "openai"
  LLM_MODEL      : model name override (e.g. "llama-3.1-8b-instant")
  GROQ_API_KEY   : required when LLM_PROVIDER=groq
  OPENAI_API_KEY : required when LLM_PROVIDER=openai

Streamlit Cloud: set these in the app's Secrets panel (Settings → Secrets).
Local dev      : put them in a .env file (loaded automatically if python-dotenv installed).
"""
import json
import logging
import os
from typing import List

from openai import OpenAI

from src.schema import Fact, FactExtraction

logger = logging.getLogger(__name__)

# ── Load .env for local development (optional dep) ────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — rely on real env vars


# ── Provider config table ──────────────────────────────────────────────────────
_PROVIDERS = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key":  "ollama",
        "default_model": "llama3.2",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": "llama-3.1-8b-instant",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
}

_EXTRACTION_SYSTEM = """\
You are an expert knowledge-graph builder for interactive fiction.

Extract ALL factual assertions from the story text and return them as a JSON
object with the key "facts" containing a list of fact objects.

Each fact MUST have exactly three string fields:
  "subject"  — the entity the fact is about (character, item, location, event)
  "relation" — the relationship type (choose from the canonical list below)
  "object"   — the target value (another entity, a boolean, a descriptive word)

CANONICAL RELATIONS (use exactly these strings):
  Character state   : isAlive, health, locatedIn, locatedAt, feels, faction
  Inventory         : hasItem, owns, carries, dropped, gave
  Relationships     : friendOf, enemyOf, alliedWith, partnerOf, marriedTo, rivalOf
  Goals             : goal, wantsTo
  Actions (events)  : attacks, kills, rescues, uses, opens, closes, speaks, commands
  Movement          : movesTo, travels
  Events            : participatedIn, occurredAt, causes
  Quests            : quest

RULES:
  - Use camelCase for relation names exactly as shown above.
  - "isAlive" object must be "true" or "false".
  - Extract inventory changes (picking up, dropping, transferring items).
  - Extract every character's location if mentioned.
  - If a character dies, emit (Character, isAlive, false).
  - If a character picks up an item, emit (Character, hasItem, ItemName).
  - Keep subject and object as proper nouns (Title Case), not pronouns.
  - Do NOT invent facts not supported by the text.
  - Output ONLY the JSON object, no explanation.
"""

_GENERATION_SYSTEM = """\
You are a creative AI story generator for an interactive narrative system.

Continue the story based on the user's input and the provided context.
The context includes:
  * Recent story segments (for narrative flow)
  * Knowledge Graph facts (established world truths)
  * Current world state (definitive character/item status)
  * Hard generation constraints (must obey)

Write one to three focused paragraphs. Be vivid and consistent.
Never contradict established facts. Never violate the constraints.\
"""


class LLMManager:
    """
    Handles LLM communication.  Backend is selected by the LLM_PROVIDER env var.
    Falls back to Ollama when no env var is set (local development default).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        provider_name = os.getenv("LLM_PROVIDER", "ollama").lower()
        cfg = _PROVIDERS.get(provider_name, _PROVIDERS["ollama"])

        # Resolve API key
        resolved_key = (
            api_key
            or os.getenv(cfg.get("api_key_env", ""), None)
            or cfg.get("api_key", "none")
        )
        resolved_url  = base_url or cfg["base_url"]
        resolved_model = model or os.getenv("LLM_MODEL", cfg["default_model"])

        self.client = OpenAI(api_key=resolved_key, base_url=resolved_url)
        self.model  = resolved_model
        self.provider = provider_name
        logger.info("LLMManager: provider=%s model=%s", provider_name, resolved_model)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_story(
        self, prompt: str, context: str, instruction: str = ""
    ) -> str:
        """Generate the next narrative segment."""
        system = _GENERATION_SYSTEM
        if instruction:
            system += f"\n\nSPECIAL INSTRUCTION:\n{instruction}"

        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"User Input: {prompt}\n\n"
                    f"Generate the next part of the story."
                ),
            },
        ]

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("Story generation error: %s", exc)
            return "The story pauses for a moment..."

    # ------------------------------------------------------------------
    # Fact extraction
    # ------------------------------------------------------------------

    def extract_facts(self, text: str) -> List[Fact]:
        """Extract structured facts from a story segment."""
        messages = [
            {"role": "system", "content": _EXTRACTION_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Extract all facts from the following story text:\n\n{text}"
                ),
            },
        ]

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            return self._parse_facts(raw)
        except Exception as exc:
            logger.error("Fact extraction error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_facts(self, raw: str) -> List[Fact]:
        """Robustly parse the LLM JSON output into a list of Fact objects."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Attempt to salvage a JSON block embedded in prose
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except Exception:
                    return []
            else:
                return []

        # Support both {"facts": [...]} and bare [...]
        if isinstance(data, list):
            raw_facts = data
        elif isinstance(data, dict):
            raw_facts = data.get("facts", [])
        else:
            return []

        facts: List[Fact] = []
        for item in raw_facts:
            if not isinstance(item, dict):
                continue
            subj = str(item.get("subject", "")).strip()
            rel = str(item.get("relation", "")).strip()
            obj = str(item.get("object", "")).strip()
            if subj and rel and obj:
                try:
                    facts.append(Fact(subject=subj, relation=rel, object=obj))
                except Exception:
                    pass

        return facts
