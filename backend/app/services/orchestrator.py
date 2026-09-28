"""The triage pipeline. Plain Python orchestration; the LLM is used at exactly one point (reflect)."""

import logging
import time
from datetime import date, datetime, time as dtime, timedelta, timezone

from sqlmodel import Session, select

from ..config import get_settings
from ..models import utcnow
from ..models import Decision, ExceptionCase, GoodsReceipt, Invoice, MemoryOp, Proposal, PurchaseOrder, TrustCell, Vendor
from ..schemas import ACTION_GUIDE, DecisionOut
from . import events, llm
from .matching import SEVERITY, detect
from .memory import MemoryUnavailable, exc_tag, memory, vendor_tag
from .narratives import case_brief, case_memory
from .policy import HIGH_RISK_CODES, LadderState, apply_guard, can_auto_resolve, update_ladder

log = logging.getLogger("munshi.orchestrator")
IST = timezone(timedelta(hours=5, minutes=30))


# --- helpers -----------------------------------------------------------------------------------

def _row(obj) -> dict:
    return obj.model_dump(mode="json") if obj is not None else None


def load_context(s: Session, invoice: Invoice) -> tuple[dict, dict, dict | None, dict | None]:
    vendor = s.get(Vendor, invoice.vendor_id)
    po = s.get(PurchaseOrder, invoice.po_ref) if invoice.po_ref else None
    if po and po.vendor_id != invoice.vendor_id:
        po = None
    grn = s.exec(select(GoodsReceipt).where(GoodsReceipt.po_id == po.id)).first() if po else None
    return _row(invoice), _row(vendor), _row(po), _row(grn)


def business_dt(d: date | str) -> datetime:
    d = d if isinstance(d, date) else date.fromisoformat(str(d))
    return datetime.combine(d, dtime(10, 0), tzinfo=IST)


def trust_cell(s: Session, vendor_id: str, code: str) -> TrustCell:
    cell = s.get(TrustCell, (vendor_id, code))
    if cell is None:
        cell = TrustCell(vendor_id=vendor_id, exc_code=code)
        s.add(cell)
        s.flush()
    return cell


# --- step 1: ingest + detect ---------------------------------------------------------------------

def ingest(s: Session, invoice: Invoice) -> ExceptionCase | None:
    """Store the invoice, run the deterministic match. Returns an ExceptionCase if anything is off."""
    s.add(invoice)
    s.flush()
    inv, vendor, po, grn = load_context(s, invoice)
    prior = [_row(p) for p in s.exec(select(Invoice).where(Invoice.vendor_id == invoice.vendor_id,
                                                           Invoice.id != invoice.id))]
    findings = detect(inv, vendor, po, grn, prior)
    if not findings:
        invoice.status = "CLEAN"
        s.commit()
        return None
    invoice.status = "EXCEPTION"
    case = ExceptionCase(
        invoice_id=invoice.id, vendor_id=invoice.vendor_id, primary_code=findings[0].code,
        findings=[f.to_dict() for f in findings], week=invoice.week,
        amount_at_stake=round(max(f.amount_at_stake for f in findings), 2),
    )
    s.add(case)
    s.commit()
    s.refresh(case)
    return case


# --- step 2: propose -----------------------------------------------------------------------------

AMNESIA_SYSTEM = (
    "You are an accounts payable assistant at an Indian manufacturer. Recommend a decision for the invoice "
    "exception below. You have NO access to past decisions, agreements or vendor history - only this invoice.\n"
    "Hard rules: never pay to changed bank details without verification (HOLD); never approve duplicates; "
    "escalate invoices above INR 5,00,000.\n" + ACTION_GUIDE +
    "\nReturn JSON with keys: action, approved_amount_inr, confidence (0-1), rationale, precedents_used (list), "
    "risk_flags (list), novel_case (bool)."
)


async def amnesia_decision(brief: str) -> DecisionOut:
    return await llm.chat_json(AMNESIA_SYSTEM, brief, DecisionOut)


def _memory_query(brief: str) -> str:
    return (
        "Recommend how the AP team should resolve this invoice exception, based on how the team has handled the "
        "same vendor and the same kind of exception before (most recent policy wins).\n\n"
        f"{brief}\n\n{ACTION_GUIDE}\n"
        "In precedents_used, list the specific past cases you relied on (date, invoice, who decided, what)."
    )


def _receipts(precedents: list[dict], limit: int = 6) -> list[dict]:
    """Prefer consolidated observations and resolved-case memories; drop near-duplicates."""
    seen, out = set(), []
    ranked = sorted(precedents, key=lambda p: (p["type"] != "observation", not p.get("document_id")))
    for p in ranked:
        key = p["text"][:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= limit:
            break
    return out


async def propose(s: Session, case: ExceptionCase, mode: str = "MEMORY") -> tuple[Proposal, bool]:
    """Produce (and store) a proposal. mode=MEMORY uses Hindsight; mode=AMNESIA is the no-memory baseline.

    Returns (proposal, auto_resolve_allowed).
    """
    settings = get_settings()
    invoice = s.get(Invoice, case.invoice_id)
    inv, vendor, po, grn = load_context(s, invoice)
    brief = case_brief(inv, vendor, case.findings, po, grn)
    started = time.monotonic()

    out: DecisionOut | None = None
    receipts: list[dict] = []
    based_on: dict = {}
    used_mode = mode

    if mode == "MEMORY" and memory.status == "on":
        try:
            try:
                receipts = _receipts(await memory.recall_precedents(
                    f"How were {case.primary_code.replace('_', ' ').lower()} exceptions from {vendor['name']} "
                    f"resolved, and why?", vendor["id"], case.primary_code, business_dt(invoice.invoice_date)))
            except Exception as e:  # receipts are nice-to-have; reflect is what matters
                log.warning("recall failed: %s", e)
            raw, based_on, err = await memory.reflect_decision(_memory_query(brief), vendor["id"])
            if raw is None:
                raw, based_on, err = await memory.reflect_decision(_memory_query(brief), vendor["id"], budget="low")
            if raw is not None:
                out = DecisionOut.model_validate(raw)
            else:
                log.warning("reflect gave no structured output: %s", err)
        except (MemoryUnavailable, Exception) as e:  # noqa: BLE001
            log.warning("memory path failed, falling back: %s", e)

    if out is None and settings.llm_enabled:
        try:
            out = await amnesia_decision(brief)
            used_mode = "AMNESIA" if mode == "AMNESIA" else "FALLBACK"
        except Exception as e:  # noqa: BLE001
            log.warning("LLM fallback failed: %s", e)

    if out is None:
        used_mode = "AMNESIA" if mode == "AMNESIA" else "FALLBACK"
        out = DecisionOut(action="HOLD", confidence=0.0, novel_case=True,
                          rationale="Could not reach a confident decision automatically - needs human review.")

    codes = [f["code"] for f in case.findings]
    guard = apply_guard(out.action, codes, invoice.total, settings.escalate_above_inr, settings.auto_resolve_max_inr)
    cell = trust_cell(s, case.vendor_id, case.primary_code)

    proposal = Proposal(
        case_id=case.id, mode=used_mode, action=guard.action, approved_amount=out.approved_amount_inr,
        confidence=out.confidence, rationale=out.rationale, risk_flags=out.risk_flags,
        precedents_used=out.precedents_used, receipts=receipts, based_on=based_on, novel_case=out.novel_case,
        guard_overrode=guard.overrode, guard_reason=guard.reason, trust_level=cell.level,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    s.add(proposal)
    if mode == "MEMORY":
        case.status = "PROPOSED"
    s.commit()
    s.refresh(proposal)
    auto_ok = mode == "MEMORY" and used_mode == "MEMORY" and can_auto_resolve(
        cell.level, guard, out.confidence, out.novel_case)
    return proposal, auto_ok


def latest_proposal(s: Session, case_id: int, mode: str = "MEMORY") -> Proposal | None:
    q = select(Proposal).where(Proposal.case_id == case_id)
    q = q.where(Proposal.mode.in_(["MEMORY", "FALLBACK"])) if mode == "MEMORY" else q.where(Proposal.mode == mode)
    return s.exec(q.order_by(Proposal.id.desc())).first()


# --- step 3: decide + learn ----------------------------------------------------------------------

async def record_decision(s: Session, case: ExceptionCase, *, action: str, decided_by: str, role: str,
                          reason: str, approved_amount: float | None = None, auto: bool = False,
                          agreed_override: bool | None = None, wait_for_memory: bool = False,
                          update_trust: bool = True) -> Decision:
    """Store the human (or auto) decision, move the trust ladder, and retain the case into Hindsight."""
    invoice = s.get(Invoice, case.invoice_id)
    vendor = s.get(Vendor, case.vendor_id)
    proposal = latest_proposal(s, case.id)

    agreed = None
    if proposal is not None:
        agreed = proposal.action == action if agreed_override is None else agreed_override

    decision = Decision(case_id=case.id, decided_by=decided_by, role=role, action=action, reason=reason,
                        approved_amount=approved_amount, agreed_with_agent=agreed, auto=auto,
                        decided_at=business_dt(invoice.invoice_date))
    s.add(decision)
    case.status = "AUTO" if auto else "RESOLVED"

    ladder_event = None
    if agreed is not None and update_trust:
        cell = trust_cell(s, case.vendor_id, case.primary_code)
        high_risk = case.primary_code in HIGH_RISK_CODES or invoice.total > get_settings().escalate_above_inr
        new, ladder_event = update_ladder(LadderState(cell.level, cell.n_decisions, cell.n_agree, cell.recent),
                                          agreed, high_risk)
        cell.level, cell.n_decisions, cell.n_agree, cell.recent = new.level, new.n_decisions, new.n_agree, new.recent
        if not agreed:
            cell.last_override_at = utcnow()
    s.commit()

    if ladder_event:
        events.publish(ladder_event, vendor=vendor.name, vendor_id=vendor.id, code=case.primary_code,
                       level=s.get(TrustCell, (case.vendor_id, case.primary_code)).level)

    await retain_case(s, case, decision, proposal, wait=wait_for_memory)
    s.refresh(decision)
    return decision


async def retain_case(s: Session, case: ExceptionCase, decision: Decision, proposal: Proposal | None,
                      wait: bool = False) -> None:
    if not memory.enabled:
        return
    invoice = s.get(Invoice, case.invoice_id)
    vendor = s.get(Vendor, case.vendor_id)
    d = decision.model_dump(mode="json") | {"business_date": invoice.invoice_date}
    text = case_memory(invoice.model_dump(mode="json"), vendor.model_dump(mode="json"), case.findings,
                       proposal.model_dump(mode="json") if proposal else None, d)
    tags = [vendor_tag(vendor.id)] + sorted({exc_tag(f["code"]) for f in case.findings}) + ["decision"]
    if decision.agreed_with_agent is False:
        tags.append("correction")
    if case.primary_code in HIGH_RISK_CODES:
        tags.append("risk")
    op = MemoryOp(kind="case", ref=f"case-{case.id}")
    s.add(op)
    s.commit()
    try:
        op.operation_id = await memory.retain(
            text, document_id=f"case-{invoice.id}", context=f"AP exception decision by {decision.decided_by}",
            tags=tags, timestamp=business_dt(invoice.invoice_date), wait=wait,
            metadata={"invoice_id": invoice.id, "vendor_id": vendor.id, "exception": case.primary_code,
                      "decision": decision.action, "decided_by": decision.decided_by,
                      "amount_inr": f"{invoice.total:.2f}", "week": str(invoice.week)},
        )
        op.status = "DONE" if wait else "PENDING"
        events.publish("memorised", case_id=case.id, vendor=vendor.name)
    except Exception as e:  # noqa: BLE001 - never lose the decision because memory failed
        op.status, op.error = "FAILED", str(e)[:300]
        log.warning("retain failed for case %s: %s", case.id, e)
    s.commit()


def severity_rank(code: str) -> int:
    return SEVERITY.index(code) if code in SEVERITY else len(SEVERITY)
