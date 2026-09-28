"""Invoice ingestion for uploads: known seed PDF -> sidecar JSON; any other PDF -> text -> Groq extraction."""

import io
import json
import uuid
from datetime import date

import pdfplumber
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import SEED_DIR
from ..models import Invoice, Vendor
from . import llm


class ExtractedLine(BaseModel):
    sku: str = ""
    description: str
    hsn: str = ""
    qty: float
    unit: str = ""
    unit_price: float
    gst_rate: float = 18


class ExtractedCharge(BaseModel):
    description: str
    amount: float
    gst_rate: float = 18


class ExtractedInvoice(BaseModel):
    vendor_name: str
    vendor_gstin: str
    invoice_no: str
    invoice_date: str
    po_ref: str | None = None
    bank_account: str = ""
    bank_ifsc: str = ""
    lines: list[ExtractedLine]
    charges: list[ExtractedCharge] = []
    subtotal: float
    gst_amount: float
    total: float


EXTRACT_SYSTEM = (
    "Extract the invoice below into JSON with keys: vendor_name, vendor_gstin, invoice_no, invoice_date "
    "(YYYY-MM-DD), po_ref, bank_account, bank_ifsc, lines (list of {sku, description, hsn, qty, unit, "
    "unit_price, gst_rate}), charges (freight/surcharges not tied to a product line: {description, amount, "
    "gst_rate}), subtotal, gst_amount (CGST+SGST or IGST), total. Numbers must be plain numbers."
)


def _seed_sidecar(invoice_id: str) -> dict | None:
    for f in (SEED_DIR / "invoices").glob("week_*.json"):
        for d in json.loads(f.read_text(encoding="utf-8")):
            if d["id"] == invoice_id:
                return d
    return None


def pdf_text(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


async def invoice_from_pdf(s: Session, filename: str, data: bytes, week: int) -> Invoice:
    stem = filename.rsplit("/", 1)[-1].removesuffix(".pdf")
    sidecar = _seed_sidecar(stem)
    if sidecar:
        return Invoice(**{**sidecar, "invoice_date": date.fromisoformat(sidecar["invoice_date"])})

    ex: ExtractedInvoice = await llm.chat_json(EXTRACT_SYSTEM, pdf_text(data)[:12000], ExtractedInvoice)
    vendors = s.exec(select(Vendor)).all()
    vendor = next((v for v in vendors if v.gstin[2:12] == ex.vendor_gstin[2:12]), None) \
        or next((v for v in vendors if v.name.lower() in ex.vendor_name.lower()
                 or ex.vendor_name.lower() in v.name.lower()), None)
    if vendor is None:
        raise ValueError(f"Unknown vendor '{ex.vendor_name}' ({ex.vendor_gstin}) - add it to the vendor master first.")
    return Invoice(
        id=f"UPL-{uuid.uuid4().hex[:8].upper()}", vendor_id=vendor.id, invoice_no=ex.invoice_no,
        invoice_date=date.fromisoformat(ex.invoice_date), po_ref=ex.po_ref, gstin=ex.vendor_gstin,
        bank_account=ex.bank_account or vendor.bank_account, bank_ifsc=ex.bank_ifsc or vendor.bank_ifsc,
        sender_email=f"accounts@{vendor.email_domain}",
        lines=[l.model_dump() for l in ex.lines], charges=[c.model_dump() for c in ex.charges],
        subtotal=ex.subtotal, gst_amount=ex.gst_amount, total=ex.total, week=week,
    )
