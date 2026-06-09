"""
Benchmark endpoints.

Benchmark runs can take minutes, so they are executed in background threads.
The frontend polls /api/benchmark/status/{job_id} until status == "done".
"""

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.benchmark import ALL_SCENARIOS, BenchmarkRunner, _pad
from src.evaluator import Evaluator

router = APIRouter()

# ── In-memory job store ───────────────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _set_job(job_id: str, **kwargs):
    with _jobs_lock:
        _jobs[job_id].update(kwargs)


# ── Request / response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    scenario: str           # "death_barrier" | "item_transfer" | "travel_event" | "relationship_change" | "all"
    scale: int = 10         # 10 | 50 | 100
    mode: str = "both"      # "ns" | "baseline" | "both"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/scenarios")
async def list_scenarios():
    """Return available benchmark scenario names and their prompt previews."""
    return {
        name: {
            "prompts_count": len(prompts),
            "first_prompt": prompts[0],
        }
        for name, prompts in ALL_SCENARIOS.items()
    }


@router.post("/run")
async def run_benchmark(body: RunRequest):
    """
    Start a benchmark run in a background thread.
    Returns a job_id that the client can poll.
    """
    if body.scenario != "all" and body.scenario not in ALL_SCENARIOS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scenario '{body.scenario}'. Choose from {list(ALL_SCENARIOS)} or 'all'",
        )
    if body.scale not in (10, 50, 100):
        raise HTTPException(status_code=422, detail="scale must be 10, 50, or 100")
    if body.mode not in ("ns", "baseline", "both"):
        raise HTTPException(status_code=422, detail="mode must be 'ns', 'baseline', or 'both'")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "request": body.model_dump(),
            "result": None,
            "error": None,
        }

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, body.scenario, body.scale, body.mode),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "running"}


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Poll job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "started_at": job["started_at"],
        "error": job.get("error"),
    }


@router.get("/results/{job_id}")
async def get_results(job_id: str):
    """Return full results for a completed job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "running":
        raise HTTPException(status_code=202, detail="Job still running")
    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=job.get("error", "Unknown error"))
    return job["result"]


@router.get("/jobs")
async def list_jobs():
    """List all benchmark jobs."""
    return [
        {
            "job_id": jid,
            "status": j["status"],
            "started_at": j["started_at"],
            "request": j["request"],
        }
        for jid, j in _jobs.items()
    ]


# ── Background worker ─────────────────────────────────────────────────────────

def _run_job(job_id: str, scenario: str, scale: int, mode: str):
    try:
        runner = BenchmarkRunner(scales=[scale])
        evaluator = Evaluator()

        if scenario == "all":
            result = runner.run_all()
        else:
            prompts = _pad(ALL_SCENARIOS[scenario], scale)
            if mode == "both":
                result = evaluator.compare_baselines(prompts, scenario_name=scenario)
            elif mode == "ns":
                result = evaluator.run_evaluation(
                    prompts, use_neurosymbolic=True, scenario_name=scenario
                )
            else:
                result = evaluator.run_evaluation(
                    prompts, use_neurosymbolic=False, scenario_name=scenario
                )

        # Sanitize result: remove non-serializable keys
        _strip_step_records(result)
        _set_job(job_id, status="done", result=result)

    except Exception as exc:
        _set_job(job_id, status="error", error=str(exc))


def _strip_step_records(obj: Any) -> None:
    """Remove step_records from nested dicts (too large for API response)."""
    if isinstance(obj, dict):
        obj.pop("step_records", None)
        for v in obj.values():
            _strip_step_records(v)
    elif isinstance(obj, list):
        for item in obj:
            _strip_step_records(item)
