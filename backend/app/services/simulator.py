"""Replays the pre-generated business weeks so the learning curve can be shown in minutes.

History weeks (1-12): invoices are triaged for real (Hindsight recall + reflect), then the scripted human
decision from the seed data is applied - exactly as if Priya's team had clicked the buttons.
Live weeks (13-14): invoices are triaged and left in the queue for a human (or auto-resolved at L2).
"""

import asyncio
import json
import logging
from datetime import date, timedelta

from sqlmodel import Session, select

from ..config import SEED_DIR, get_settings
from ..db import engine
from ..models import ExceptionCase, Invoice, MemoryOp, SimState
from . import events
from .memory import memory
from .orchestrator import business_dt, ingest, propose, record_decision

log = logging.getLogger("munshi.simulator")

HISTORY_WEEKS = 12
LAST_WEEK = 14
_lock = asyncio.Lock()


def week_file(week: int):
    return SEED_DIR / "invoices" / f"week_{week:02d}.json"


def load_week(week: int) -> list[dict]:
    f = week_file(week)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def week_start(week: int) -> date:
    meta = json.loads((SEED_DIR / "meta.json").read_text(encoding="utf-8"))
    return date.fromisoformat(meta["week1_start"]) + timedelta(weeks=week - 1)


def current_week() -> int:
    with Session(engine) as s:
        return s.get(SimState, 1).current_week


def _invoice_from_seed(d: dict) -> Invoice:
    return Invoice(**{**d, "invoice_date": date.fromisoformat(d["invoice_date"])})


async def retain_background(up_to: date) -> int:
    """Retain agreements, emails and policy notes dated on or before `up_to` (once each)."""
    if not memory.enabled:
        return 0
    items = json.loads((SEED_DIR / "background.json").read_text(encoding="utf-8"))
    n = 0
    with Session(engine) as s:
        done = {o.ref for o in s.exec(select(MemoryOp).where(MemoryOp.kind == "background",
                                                             MemoryOp.status == "DONE"))}
        for item in items:
            if item["id"] in done or date.fromisoformat(item["date"]) > up_to:
                continue
            op = MemoryOp(kind="background", ref=item["id"])
            s.add(op)
            try:
                op.operation_id = await memory.retain(
                    item["content"], document_id=item["id"], context=item["context"], tags=item["tags"],
                    timestamp=business_dt(item["date"]), wait=True, metadata={"source": item["context"]})
                op.status = "DONE"
                n += 1
            except Exception as e:  # noqa: BLE001
                op.status, op.error = "FAILED", str(e)[:300]
            s.commit()
    return n


async def _triage_one(case_id: int, history: bool, sem: asyncio.Semaphore) -> dict:
    async with sem:
        with Session(engine) as s:
            case = s.get(ExceptionCase, case_id)
            invoice = s.get(Invoice, case.invoice_id)
            proposal, auto_ok = await propose(s, case)
            gt = invoice.ground_truth or {}
            result = {"case_id": case_id, "action": proposal.action, "auto": False,
                      "correct": gt.get("action") == proposal.action if gt else None}

            if auto_ok:
                result["auto"] = True
                if history and gt:
                    # Auto-resolved, then checked by a human in the daily digest review.
                    agreed = gt["action"] == proposal.action
                    await record_decision(
                        s, case, action=proposal.action if agreed else gt["action"],
                        decided_by="Munshi" if agreed else gt["decided_by"], role=gt.get("role", ""),
                        reason=proposal.rationale if agreed else gt["reason"], auto=True,
                        approved_amount=gt.get("approved_amount"), agreed_override=agreed, wait_for_memory=True)
                else:
                    await record_decision(s, case, action=proposal.action, decided_by="Munshi", role="AP agent",
                                          reason=proposal.rationale, auto=True, update_trust=False,
                                          approved_amount=proposal.approved_amount)
                events.publish("auto_resolved", case_id=case_id, action=proposal.action)
            elif history and gt:
                await record_decision(s, case, action=gt["action"], decided_by=gt["decided_by"],
                                      role=gt.get("role", ""), reason=gt["reason"],
                                      approved_amount=gt.get("approved_amount"), wait_for_memory=True)
            return result


async def run_week(week: int | None = None) -> dict:
    """Process the next business week (or a specific one)."""
    async with _lock:
        week = week or current_week() + 1
        if week > LAST_WEEK:
            return {"week": current_week(), "done": True, "message": "All simulated weeks processed."}
        history = week <= HISTORY_WEEKS
        events.publish("week_started", week=week)

        n_bg = await retain_background(week_start(week) + timedelta(days=6))

        case_ids: list[int] = []
        n_invoices = 0
        with Session(engine) as s:
            for d in sorted(load_week(week), key=lambda x: x["invoice_date"]):
                if s.get(Invoice, d["id"]):
                    continue  # idempotent re-run
                n_invoices += 1
                case = ingest(s, _invoice_from_seed(d))
                if case:
                    case_ids.append(case.id)

        sem = asyncio.Semaphore(max(1, get_settings().sim_concurrency))
        results = await asyncio.gather(*[_triage_one(cid, history, sem) for cid in case_ids],
                                       return_exceptions=True)
        errors = [str(r) for r in results if isinstance(r, Exception)]
        for e in errors:
            log.error("triage failed: %s", e)
        ok = [r for r in results if isinstance(r, dict)]

        with Session(engine) as s:
            s.get(SimState, 1).current_week = week
            s.commit()

        summary = {
            "week": week, "history": history, "invoices": n_invoices, "exceptions": len(case_ids),
            "auto_resolved": sum(r["auto"] for r in ok),
            "correct": sum(1 for r in ok if r["correct"]), "graded": sum(1 for r in ok if r["correct"] is not None),
            "background_memories": n_bg, "errors": errors[:5],
        }
        events.publish("week_done", **summary)
        return summary
