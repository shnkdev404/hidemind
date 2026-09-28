"""SQLite tables. Exact, auditable facts live here - learned knowledge lives in Hindsight."""

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json(default=None):
    return Field(default_factory=(lambda: default() if callable(default) else default),
                 sa_column=Column(JSON))


class Vendor(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    city: str
    gstin: str
    msme: bool = False
    email_domain: str
    bank_account: str
    bank_ifsc: str
    bank_verified_on: date
    category: str = ""


class PurchaseOrder(SQLModel, table=True):
    id: str = Field(primary_key=True)
    vendor_id: str = Field(index=True)
    po_date: date
    lines: list[dict[str, Any]] = _json(list)


class GoodsReceipt(SQLModel, table=True):
    id: str = Field(primary_key=True)
    po_id: str = Field(index=True)
    received_date: date
    lines: list[dict[str, Any]] = _json(list)


class Invoice(SQLModel, table=True):
    id: str = Field(primary_key=True)
    vendor_id: str = Field(index=True)
    invoice_no: str = Field(index=True)
    invoice_date: date
    po_ref: Optional[str] = None
    gstin: str
    bank_account: str
    bank_ifsc: str
    sender_email: str
    lines: list[dict[str, Any]] = _json(list)
    charges: list[dict[str, Any]] = _json(list)
    subtotal: float
    gst_amount: float
    total: float
    week: int = Field(index=True)
    pdf_path: Optional[str] = None
    status: str = "NEW"  # NEW | CLEAN | EXCEPTION
    # Scripted human decision (history weeks) / ground truth (eval weeks). Never sent to the LLM.
    ground_truth: Optional[dict[str, Any]] = _json(None)


class ExceptionCase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: str = Field(index=True, unique=True)
    vendor_id: str = Field(index=True)
    primary_code: str = Field(index=True)
    findings: list[dict[str, Any]] = _json(list)
    amount_at_stake: float = 0
    week: int = Field(index=True)
    status: str = "OPEN"  # OPEN | PROPOSED | RESOLVED | AUTO
    created_at: datetime = Field(default_factory=utcnow)


class Proposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True)
    mode: str = "MEMORY"  # MEMORY | AMNESIA | FALLBACK
    action: str
    approved_amount: Optional[float] = None
    confidence: float = 0
    rationale: str = ""
    risk_flags: list[str] = _json(list)
    precedents_used: list[str] = _json(list)
    receipts: list[dict[str, Any]] = _json(list)
    based_on: dict[str, Any] = _json(dict)
    novel_case: bool = False
    guard_overrode: bool = False
    guard_reason: Optional[str] = None
    trust_level: int = 0
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Decision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True, unique=True)
    decided_by: str
    role: str = ""
    action: str
    approved_amount: Optional[float] = None
    reason: str = ""
    agreed_with_agent: Optional[bool] = None
    auto: bool = False
    decided_at: datetime = Field(default_factory=utcnow)


class TrustCell(SQLModel, table=True):
    vendor_id: str = Field(primary_key=True)
    exc_code: str = Field(primary_key=True)
    level: int = 0
    n_decisions: int = 0
    n_agree: int = 0
    recent: list[bool] = _json(list)  # newest last, capped at 10
    last_override_at: Optional[datetime] = None


class SimState(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    current_week: int = 0


class MemoryOp(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str  # case | background
    ref: str = Field(index=True)
    operation_id: Optional[str] = None
    status: str = "PENDING"  # PENDING | DONE | FAILED
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
