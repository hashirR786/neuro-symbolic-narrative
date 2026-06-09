"""Session management endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from backend.app.session_manager import session_manager

router = APIRouter()


def _resolve_session_id(x_session_id: Optional[str]) -> str:
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    return x_session_id


@router.post("/new")
async def new_session():
    """Create a new session and return its ID."""
    session_id = str(uuid.uuid4())
    data = session_manager.get_or_create(session_id)
    return {
        "session_id": session_id,
        "welcome": data["history"][0]["content"],
    }


@router.get("/info")
async def session_info(x_session_id: Optional[str] = Header(default=None)):
    """Return basic info about an existing session."""
    sid = _resolve_session_id(x_session_id)
    data = session_manager.get(sid)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = data["engine"]
    return {
        "session_id": sid,
        "created_at": data["created_at"].isoformat(),
        "total_steps": engine.total_steps,
        "history_length": len(data["history"]),
        "violations": len(data["violation_log"]),
    }


@router.post("/reset")
async def reset_session(x_session_id: Optional[str] = Header(default=None)):
    """Reset the engine, history and violation log for a session."""
    sid = _resolve_session_id(x_session_id)
    data = session_manager.reset(sid)
    return {
        "session_id": sid,
        "status": "reset",
        "welcome": data["history"][0]["content"],
    }


@router.delete("/")
async def delete_session(x_session_id: Optional[str] = Header(default=None)):
    """Delete a session entirely."""
    sid = _resolve_session_id(x_session_id)
    session_manager.delete(sid)
    return {"session_id": sid, "status": "deleted"}
