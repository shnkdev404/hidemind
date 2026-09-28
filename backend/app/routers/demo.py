import asyncio
import logging

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from ..config import get_settings
from ..db import engine, reset_db
from ..models import Vendor
from ..services import events, simulator, snapshots
from ..services.memory import memory

router = APIRouter(prefix="/api", tags=["demo"])
log = logging.getLogger("munshi.demo")
_task: asyncio.Task | None = None


@router.get("/health")
def health():
    s = get_settings()
    week = simulator.current_week()
    return {
        "memory": memory.status, "memory_error": memory.last_error, "bank_id": s.bank_id,
        "llm": "on" if s.llm_enabled else "off", "model": s.agent_model,
        "week": week, "business_date": str(simulator.week_start(max(week, 1))),
        "last_week": simulator.LAST_WEEK, "history_weeks": simulator.HISTORY_WEEKS,
        "simulating": bool(_task and not _task.done()),
    }


async def _run(week: int | None):
    try:
        await simulator.run_week(week)
    except Exception as e:  # noqa: BLE001
        log.exception("simulation failed")
        events.publish("error", message=f"Simulation failed: {e}")


@router.post("/simulate/next-week")
async def simulate_next_week(wait: bool = False):
    global _task
    if _task and not _task.done():
        raise HTTPException(409, "A week is already being simulated")
    if wait:
        return await simulator.run_week()
    _task = asyncio.create_task(_run(None))
    return {"started": True, "week": simulator.current_week() + 1}


@router.get("/demo/snapshots")
def list_snapshots():
    return snapshots.list_snapshots()


@router.post("/demo/snapshot")
async def take_snapshot(name: str):
    await snapshots.save(name)
    return {"saved": name}


@router.post("/demo/reset")
async def reset(to: str = "week0"):
    """Restore a named snapshot (e.g. week0, week12). 'week0' falls back to a fresh start if no snapshot exists."""
    if _task and not _task.done():
        raise HTTPException(409, "Wait for the running simulation to finish")
    if to in snapshots.list_snapshots():
        await snapshots.restore(to)
    elif to == "week0":
        reset_db()
        if memory.enabled:
            await memory.delete_bank()
            with Session(engine) as s:
                vendors = [v.model_dump(mode="json") for v in s.exec(select(Vendor)).all()]
            await memory.setup_bank(vendors)
    else:
        raise HTTPException(404, f"No snapshot '{to}'")
    events.publish("reset", to=to)
    return {"reset": to, "week": simulator.current_week()}


@router.get("/events")
async def stream():
    return EventSourceResponse(events.subscribe(), ping=15)
