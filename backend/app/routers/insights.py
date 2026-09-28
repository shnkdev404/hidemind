from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Decision, ExceptionCase, Invoice, MemoryOp, TrustCell, Vendor
from ..schemas import AskIn
from ..services import metrics
from ..services.matching import EXCEPTION_LABELS, SEVERITY
from ..services.memory import FRAUD_ID, PLAYBOOK_ID, MemoryUnavailable, dossier_id, memory
from ..services.policy import LEVEL_NAMES

router = APIRouter(prefix="/api", tags=["insights"])


def _need_memory():
    if not memory.enabled:
        raise HTTPException(503, "Hindsight is not configured (set HINDSIGHT_URL in .env)")


async def _model(mm_id: str) -> dict:
    _need_memory()
    try:
        return await memory.get_model(mm_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Hindsight: {e}") from e


@router.get("/trust")
def trust_grid(s: Session = Depends(get_session)):
    vendors = s.exec(select(Vendor).order_by(Vendor.name)).all()
    cells = s.exec(select(TrustCell)).all()
    codes = sorted({c.exc_code for c in cells}, key=SEVERITY.index)
    return {
        "vendors": [{"id": v.id, "name": v.name} for v in vendors],
        "codes": [{"code": c, "label": EXCEPTION_LABELS[c]} for c in codes],
        "cells": [c.model_dump(mode="json") | {"level_name": LEVEL_NAMES[c.level]} for c in cells],
    }


@router.get("/vendors")
def vendors(s: Session = Depends(get_session)):
    out = []
    for v in s.exec(select(Vendor).order_by(Vendor.name)).all():
        n_inv = len(s.exec(select(Invoice.id).where(Invoice.vendor_id == v.id)).all())
        n_exc = len(s.exec(select(ExceptionCase.id).where(ExceptionCase.vendor_id == v.id)).all())
        out.append(v.model_dump(mode="json", exclude={"bank_account"}) |
                   {"bank_account": f"•••• {v.bank_account[-4:]}", "invoices": n_inv, "exceptions": n_exc})
    return out


@router.get("/vendors/{vendor_id}")
async def vendor_detail(vendor_id: str, s: Session = Depends(get_session)):
    v = s.get(Vendor, vendor_id)
    if not v:
        raise HTTPException(404, "vendor not found")
    history = []
    for c in s.exec(select(ExceptionCase).where(ExceptionCase.vendor_id == vendor_id).order_by(ExceptionCase.id)):
        d = s.exec(select(Decision).where(Decision.case_id == c.id)).first()
        inv = s.get(Invoice, c.invoice_id)
        history.append({"case_id": c.id, "week": c.week, "date": str(inv.invoice_date), "invoice_no": inv.invoice_no,
                        "code": c.primary_code, "total": inv.total,
                        "decision": d.action if d else None, "decided_by": d.decided_by if d else None,
                        "reason": d.reason if d else None, "auto": d.auto if d else False})
    dossier, err = None, None
    if memory.enabled:
        try:
            dossier = await memory.get_model(dossier_id(vendor_id))
        except Exception as e:  # noqa: BLE001
            err = str(e)[:200]
    return {"vendor": v.model_dump(mode="json", exclude={"bank_account"}) | {"bank_account": f"•••• {v.bank_account[-4:]}"},
            "history": history, "dossier": dossier, "dossier_error": err}


@router.get("/playbook")
async def playbook():
    return await _model(PLAYBOOK_ID)


@router.get("/playbook/history")
async def playbook_history():
    _need_memory()
    try:
        return await memory.model_history(PLAYBOOK_ID)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Hindsight: {e}") from e


@router.get("/fraud-watchlist")
async def fraud_watchlist():
    return await _model(FRAUD_ID)


@router.get("/memory/overview")
async def memory_overview():
    _need_memory()
    return await memory.overview()


@router.get("/memory/items")
async def memory_items(type: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0):
    _need_memory()
    try:
        return await memory.list_items(type, q, min(limit, 200), offset)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Hindsight: {e}") from e


@router.get("/memory/recall")
async def memory_recall(q: str, vendor: str | None = None):
    """Run a raw Hindsight recall (semantic + keyword + graph + temporal) and show exactly what comes back."""
    _need_memory()
    try:
        return await memory.raw_recall(q, [f"vendor:{vendor.lower()}"] if vendor else None)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Hindsight: {e}") from e


@router.get("/memory/log")
def memory_log(limit: int = 50, s: Session = Depends(get_session)):
    """Local audit trail of every retain Munshi sent to Hindsight."""
    ops = s.exec(select(MemoryOp).order_by(MemoryOp.id.desc()).limit(limit)).all()
    return [o.model_dump(mode="json") for o in ops]


@router.post("/memory/refresh")
async def refresh_models(s: Session = Depends(get_session)):
    _need_memory()
    await memory.refresh_all([v.id for v in s.exec(select(Vendor)).all()])
    return {"ok": True}


@router.post("/ask")
async def ask(body: AskIn):
    _need_memory()
    try:
        return await memory.ask(body.question)
    except MemoryUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Hindsight: {e}") from e


@router.get("/metrics")
def get_metrics(s: Session = Depends(get_session)):
    return metrics.summary(s)
