"""Story generation and history endpoints."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.app.session_manager import session_manager
from src.schema import ViolationReport

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)


class GenerateRequest(BaseModel):
    user_input: str


def _resolve(x_session_id: Optional[str]):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    data = session_manager.get_or_create(x_session_id)
    return data


@router.post("/generate")
async def generate_story(
    body: GenerateRequest,
    x_session_id: Optional[str] = Header(default=None),
):
    """
    Generate the next story beat via the full neuro-symbolic pipeline.

    Runs engine.generate_step() in a thread pool (it is synchronous and
    can take several seconds for LLM + verification rounds).
    """
    data = _resolve(x_session_id)
    engine = data["engine"]
    history = data["history"]
    violation_log = data["violation_log"]

    user_input = body.user_input.strip()
    if not user_input:
        raise HTTPException(status_code=422, detail="user_input must not be empty")

    # Add user message to history
    history.append({"role": "user", "content": user_input})

    # Run synchronous pipeline in thread pool
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, engine.generate_step, user_input)

    story_beat = result["text"]
    corrections = result["corrections_made"]
    violations = [ViolationReport(**v) for v in result.get("violations", [])]

    # Append correction notice inline (mirrors Streamlit behaviour)
    response_content = story_beat
    if corrections > 0:
        response_content += (
            f"\n\n> ⚠️ **System**: Prevented {corrections} inconsistency error(s) "
            f"through automated verify-rewrite loops."
        )

    history.append({"role": "assistant", "content": response_content})

    if violations:
        violation_log.extend(result["violations"])

    return {
        "story_beat": response_content,
        "raw_text": story_beat,
        "verification_passed": result["is_consistent"],
        "rewrite_count": corrections,
        "facts": result["facts"],
        "violations": result["violations"],
    }


@router.get("/history")
async def get_history(x_session_id: Optional[str] = Header(default=None)):
    """Return the full chat history for a session."""
    data = _resolve(x_session_id)
    return {"history": data["history"]}


@router.get("/violations")
async def get_violations(x_session_id: Optional[str] = Header(default=None)):
    """Return the accumulated violation log for a session."""
    data = _resolve(x_session_id)
    return {
        "violations": data["violation_log"],
        "total": len(data["violation_log"]),
    }


@router.delete("/violations")
async def clear_violations(x_session_id: Optional[str] = Header(default=None)):
    """Clear the violation log."""
    data = _resolve(x_session_id)
    data["violation_log"].clear()
    return {"status": "cleared"}


@router.get("/facts")
async def get_recent_facts(
    n: int = 30,
    x_session_id: Optional[str] = Header(default=None),
):
    """Return the most recent N KG facts as strings."""
    data = _resolve(x_session_id)
    engine = data["engine"]
    facts = engine.kg.get_recent_facts_strings(n)
    return {"facts": list(reversed(facts)), "total": len(facts)}


@router.get("/state")
async def get_world_state(x_session_id: Optional[str] = Header(default=None)):
    """Return current world state (characters, items, locations, timeline)."""
    data = _resolve(x_session_id)
    engine = data["engine"]
    ws = engine.world_state
    return ws.snapshot()
