from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..config import ROOT_DIR
from ..db import get_session
from ..models import Decision, ExceptionCase, Invoice, TrustCell, Vendor
from ..schemas import DecideIn
from ..services import events
from ..services.ingestion import invoice_from_pdf
from ..services.matching import EXCEPTION_LABELS
from ..services.orchestrator import ingest, latest_proposal, load_context, propose, record_decision
from ..services.policy import LEVEL_NAMES
from ..services.simulator import current_week

router = APIRouter(prefix="/api", tags=["cases"])


def mask(acct: str) -> str:
    return f"•••• {acct[-4:]}" if acct else ""


def proposal_out(p) -> dict | None:
    if p is None:
        return None
    return p.model_dump(mode="json", exclude={"based_on"}) | {
        "trust_level_name": LEVEL_NAMES.get(p.trust_level, "Intern"),
        "based_on": p.based_on,
    }


def case_summary(s: Session, c: ExceptionCase, vendors: dict[str, Vendor]) -> dict:
    inv = s.get(Invoice, c.invoice_id)
    p = latest_proposal(s, c.id)
    d = s.exec(select(Decision).where(Decision.case_id == c.id)).first()
    cell = s.get(TrustCell, (c.vendor_id, c.primary_code))
    return {
        "id": c.id, "invoice_id": inv.id, "invoice_no": inv.invoice_no, "invoice_date": str(inv.invoice_date),
        "vendor_id": c.vendor_id, "vendor": vendors[c.vendor_id].name, "week": c.week,
        "primary_code": c.primary_code, "label": EXCEPTION_LABELS.get(c.primary_code, c.primary_code),
        "codes": [f["code"] for f in c.findings], "amount_at_stake": c.amount_at_stake, "total": inv.total,
        "status": c.status,
        "proposal": {"action": p.action, "confidence": p.confidence, "mode": p.mode,
                     "guard_overrode": p.guard_overrode, "novel_case": p.novel_case} if p else None,
        "decision": {"action": d.action, "auto": d.auto, "decided_by": d.decided_by,
                     "agreed": d.agreed_with_agent} if d else None,
        "trust_level": cell.level if cell else 0,
    }


@router.get("/queue")
def queue(status: str = "open", week: int | None = None, s: Session = Depends(get_session)):
    q = select(ExceptionCase)
    if status == "open":
        q = q.where(ExceptionCase.status.in_(["OPEN", "PROPOSED"]))
    elif status == "resolved":
        q = q.where(ExceptionCase.status.in_(["RESOLVED", "AUTO"]))
    if week is not None:
        q = q.where(ExceptionCase.week == week)
    vendors = {v.id: v for v in s.exec(select(Vendor)).all()}
    cases = s.exec(q.order_by(ExceptionCase.week.desc(), ExceptionCase.id.desc())).all()
    return [case_summary(s, c, vendors) for c in cases]


@router.get("/cases/{case_id}")
def case_detail(case_id: int, s: Session = Depends(get_session)):
    c = s.get(ExceptionCase, case_id)
    if not c:
        raise HTTPException(404, "case not found")
    invoice = s.get(Invoice, c.invoice_id)
    inv, vendor, po, grn = load_context(s, invoice)
    inv.pop("ground_truth", None)
    inv["bank_account"] = mask(inv["bank_account"])
    vendor["bank_account"] = mask(vendor["bank_account"])
    d = s.exec(select(Decision).where(Decision.case_id == c.id)).first()
    cell = s.get(TrustCell, (c.vendor_id, c.primary_code))
    return {
        "case": c.model_dump(mode="json") | {"label": EXCEPTION_LABELS.get(c.primary_code, c.primary_code)},
        "invoice": inv, "vendor": vendor, "po": po, "grn": grn,
        "proposal": proposal_out(latest_proposal(s, c.id)),
        "amnesia": proposal_out(latest_proposal(s, c.id, mode="AMNESIA")),
        "decision": d.model_dump(mode="json") if d else None,
        "trust": {"level": cell.level if cell else 0, "name": LEVEL_NAMES.get(cell.level if cell else 0),
                  "n_decisions": cell.n_decisions if cell else 0, "n_agree": cell.n_agree if cell else 0},
    }


@router.post("/cases/{case_id}/decide")
async def decide(case_id: int, body: DecideIn, s: Session = Depends(get_session)):
    c = s.get(ExceptionCase, case_id)
    if not c:
        raise HTTPException(404, "case not found")
    if s.exec(select(Decision).where(Decision.case_id == case_id)).first():
        raise HTTPException(409, "case already decided")
    d = await record_decision(s, c, action=body.action, decided_by=body.decided_by, role=body.role,
                              reason=body.reason, approved_amount=body.approved_amount)
    return d.model_dump(mode="json")


@router.post("/cases/{case_id}/propose")
async def repropose(case_id: int, mode: str = "MEMORY", s: Session = Depends(get_session)):
    """mode=MEMORY re-runs Munshi; mode=AMNESIA runs the no-memory baseline for the side-by-side view."""
    c = s.get(ExceptionCase, case_id)
    if not c:
        raise HTTPException(404, "case not found")
    p, _ = await propose(s, c, mode="AMNESIA" if mode.upper() == "AMNESIA" else "MEMORY")
    return proposal_out(p)


@router.post("/invoices/upload")
async def upload(file: UploadFile = File(...), s: Session = Depends(get_session)):
    data = await file.read()
    try:
        invoice = await invoice_from_pdf(s, file.filename or "upload.pdf", data, max(current_week(), 1))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Could not read invoice: {e}") from e
    if s.get(Invoice, invoice.id):
        raise HTTPException(409, f"Invoice {invoice.id} already ingested")
    case = ingest(s, invoice)
    if case is None:
        return {"invoice_id": invoice.id, "status": "CLEAN", "case_id": None}
    await propose(s, case)
    events.publish("invoice_ingested", case_id=case.id)
    return {"invoice_id": invoice.id, "status": "EXCEPTION", "case_id": case.id}


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: str, s: Session = Depends(get_session)):
    inv = s.get(Invoice, invoice_id)
    if not inv or not inv.pdf_path or not (ROOT_DIR / inv.pdf_path).exists():
        raise HTTPException(404, "PDF not found")
    return FileResponse(ROOT_DIR / inv.pdf_path, media_type="application/pdf")
