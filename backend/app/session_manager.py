"""
Server-side session store.

Maps  session_id (UUID str) → {
    "engine"        : StoryEngine,
    "history"       : List[{"role": str, "content": str}],
    "violation_log" : List[dict],
    "created_at"    : datetime,
}

The StoryEngine instance contains all in-memory FAISS + NetworkX state.
"""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional

from src.story_engine import StoryEngine

logger = logging.getLogger(__name__)

_WELCOME = (
    "Welcome to the **Neuro-Symbolic RAG Interactive Narrative**.\n\n"
    "Begin your story by introducing a character and a setting. "
    "The system will track every established fact in a live Knowledge Graph "
    "and automatically detect and correct narrative inconsistencies."
)


class SessionManager:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_create(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = self._new_session()
                logger.info("Created session %s", session_id)
            return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

    def reset(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            self._sessions[session_id] = self._new_session()
            logger.info("Reset session %s", session_id)
            return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            logger.info("Deleted session %s", session_id)

    def list_sessions(self):
        return [
            {
                "session_id": sid,
                "created_at": data["created_at"].isoformat(),
                "steps": data["engine"].total_steps,
            }
            for sid, data in self._sessions.items()
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _new_session() -> Dict[str, Any]:
        return {
            "engine": StoryEngine(use_neurosymbolic=True),
            "history": [{"role": "assistant", "content": _WELCOME}],
            "violation_log": [],
            "created_at": datetime.utcnow(),
        }


# Module-level singleton
session_manager = SessionManager()
