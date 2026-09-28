"""Deterministic 3-way match + exception detectors.

Pure functions over plain dicts: no DB, no network, no LLM. Money math never goes through an LLM.
"""

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

PRICE_TOLERANCE_PCT = 0.5
TAX_TOLERANCE_INR = 0.01
DUPLICATE_WINDOW_DAYS = 30

# Highest first - the primary code of a case drives its trust-ladder cell.
SEVERITY = [
    "BANK_CHANGE", "DUPLICATE", "GSTIN_MISMATCH", "NO_PO",
    "QTY_VAR", "PRICE_VAR", "UNPO_CHARGE", "TAX_CALC",
]

EXCEPTION_LABELS = {
    "BANK_CHANGE": "Bank details changed",
    "DUPLICATE": "Possible duplicate",
    "GSTIN_MISMATCH": "GSTIN mismatch",
    "NO_PO": "No purchase order",
    "QTY_VAR": "Quantity > received",
    "PRICE_VAR": "Price variance vs PO",
    "UNPO_CHARGE": "Charge not on PO",
    "TAX_CALC": "GST calculation error",
}


@dataclass
class Finding:
    code: str
    summary: str
    amount_at_stake: float = 0.0
    variance_pct: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_date(d: Any) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d))


def expected_gst(lines: list[dict], charges: list[dict]) -> float:
    total = sum(l["qty"] * l["unit_price"] * l["gst_rate"] / 100 for l in lines)
    total += sum(c["amount"] * c.get("gst_rate", 18) / 100 for c in charges)
    return round(total, 2)


def detect(
    invoice: dict,
    vendor: dict,
    po: dict | None,
    grn: dict | None,
    prior_invoices: list[dict],
) -> list[Finding]:
    """Return every exception on this invoice, most severe first."""
    findings: list[Finding] = []

    # --- Vendor master checks -------------------------------------------------
    if invoice["bank_account"] != vendor["bank_account"] or invoice["bank_ifsc"] != vendor["bank_ifsc"]:
        findings.append(Finding(
            "BANK_CHANGE",
            f"Invoice asks for payment to A/c ••{invoice['bank_account'][-4:]} ({invoice['bank_ifsc']}); "
            f"verified master is A/c ••{vendor['bank_account'][-4:]} ({vendor['bank_ifsc']}).",
            amount_at_stake=invoice["total"],
            detail={
                "invoice_bank": f"{invoice['bank_ifsc']} ••{invoice['bank_account'][-4:]}",
                "master_bank": f"{vendor['bank_ifsc']} ••{vendor['bank_account'][-4:]}",
                "master_verified_on": str(vendor["bank_verified_on"]),
                "sender_email": invoice["sender_email"],
                "sender_domain_matches_master": invoice["sender_email"].split("@")[-1] == vendor["email_domain"],
            },
        ))

    if invoice["gstin"] != vendor["gstin"]:
        findings.append(Finding(
            "GSTIN_MISMATCH",
            f"Invoice GSTIN {invoice['gstin']} differs from vendor master {vendor['gstin']}.",
            amount_at_stake=invoice["gst_amount"],
            detail={"invoice_gstin": invoice["gstin"], "master_gstin": vendor["gstin"],
                    "same_pan": invoice["gstin"][2:12] == vendor["gstin"][2:12]},
        ))

    # --- Duplicates -------------------------------------------------------------
    inv_date = _as_date(invoice["invoice_date"])
    for prior in prior_invoices:
        if prior["id"] == invoice["id"] or prior["vendor_id"] != invoice["vendor_id"]:
            continue
        same_no = prior["invoice_no"] == invoice["invoice_no"]
        near = (abs((inv_date - _as_date(prior["invoice_date"])).days) <= DUPLICATE_WINDOW_DAYS
                and abs(prior["total"] - invoice["total"]) < 1 and prior.get("po_ref") == invoice.get("po_ref"))
        if same_no or near:
            findings.append(Finding(
                "DUPLICATE",
                f"Matches earlier invoice {prior['invoice_no']} dated {prior['invoice_date']} "
                f"(₹{prior['total']:,.2f})" + (" - same invoice number." if same_no else " - same amount and PO."),
                amount_at_stake=invoice["total"],
                detail={"original_invoice_id": prior["id"], "original_invoice_no": prior["invoice_no"],
                        "original_date": str(prior["invoice_date"]), "same_number": same_no},
            ))
            break

    # --- PO checks --------------------------------------------------------------
    if not po:
        history = [p["total"] for p in prior_invoices
                   if p["vendor_id"] == invoice["vendor_id"] and p["id"] != invoice["id"]]
        avg = round(sum(history) / len(history), 2) if history else None
        findings.append(Finding(
            "NO_PO",
            "Invoice has no valid purchase order reference."
            + (f" Vendor's average past invoice: ₹{avg:,.2f} ({(invoice['total'] / avg - 1) * 100:+.1f}% vs this one)."
               if avg else " No prior invoices from this vendor."),
            amount_at_stake=invoice["total"],
            variance_pct=round((invoice["total"] / avg - 1) * 100, 2) if avg else None,
            detail={"po_ref": invoice.get("po_ref"), "vendor_avg_total": avg, "n_prior": len(history)},
        ))
    else:
        po_lines = {l["sku"]: l for l in po["lines"]}
        grn_qty = {l["sku"]: l["qty_received"] for l in (grn["lines"] if grn else [])}
        price_lines, qty_lines = [], []
        for line in invoice["lines"]:
            pl = po_lines.get(line["sku"])
            if pl is None:
                findings.append(Finding(
                    "UNPO_CHARGE",
                    f"Line '{line['description']}' (₹{line['qty'] * line['unit_price']:,.2f}) is not on {po['id']}.",
                    amount_at_stake=round(line["qty"] * line["unit_price"], 2),
                    detail={"description": line["description"], "amount": round(line["qty"] * line["unit_price"], 2)},
                ))
                continue
            var = (line["unit_price"] - pl["unit_price"]) / pl["unit_price"] * 100
            if abs(var) > PRICE_TOLERANCE_PCT:
                price_lines.append({"sku": line["sku"], "description": line["description"],
                                    "po_price": pl["unit_price"], "invoice_price": line["unit_price"],
                                    "qty": line["qty"], "variance_pct": round(var, 2),
                                    "extra": round((line["unit_price"] - pl["unit_price"]) * line["qty"], 2)})
            received = grn_qty.get(line["sku"], 0)
            if line["qty"] > received:
                qty_lines.append({"sku": line["sku"], "description": line["description"],
                                  "invoiced_qty": line["qty"], "received_qty": received, "unit": line.get("unit", ""),
                                  "extra": round((line["qty"] - received) * line["unit_price"], 2)})
        if price_lines:
            worst = max(price_lines, key=lambda p: abs(p["variance_pct"]))
            findings.append(Finding(
                "PRICE_VAR",
                f"Unit price {worst['variance_pct']:+.2f}% vs {po['id']} on '{worst['description']}' "
                f"(₹{worst['invoice_price']:,.2f} vs ₹{worst['po_price']:,.2f}).",
                amount_at_stake=round(sum(p["extra"] for p in price_lines), 2),
                variance_pct=worst["variance_pct"],
                detail={"lines": price_lines},
            ))
        if qty_lines:
            q = qty_lines[0]
            findings.append(Finding(
                "QTY_VAR",
                f"Invoiced {q['invoiced_qty']} {q['unit']} of '{q['description']}' but GRN shows {q['received_qty']} received.",
                amount_at_stake=round(sum(x["extra"] for x in qty_lines), 2),
                variance_pct=round((q["invoiced_qty"] - q["received_qty"]) / q["invoiced_qty"] * 100, 2),
                detail={"lines": qty_lines, "grn_id": grn["id"] if grn else None},
            ))

    for c in invoice.get("charges", []):
        findings.append(Finding(
            "UNPO_CHARGE",
            f"'{c['description']}' of ₹{c['amount']:,.2f} is not on the purchase order"
            + (f" ({c['amount'] / invoice['subtotal'] * 100:.2f}% of goods value)." if invoice["subtotal"] else "."),
            amount_at_stake=c["amount"],
            variance_pct=round(c["amount"] / invoice["subtotal"] * 100, 2) if invoice["subtotal"] else None,
            detail={"description": c["description"], "amount": c["amount"]},
        ))

    # --- Tax --------------------------------------------------------------------
    exp = expected_gst(invoice["lines"], invoice.get("charges", []))
    diff = round(invoice["gst_amount"] - exp, 2)
    if abs(diff) > TAX_TOLERANCE_INR:
        findings.append(Finding(
            "TAX_CALC",
            f"GST charged ₹{invoice['gst_amount']:,.2f} vs computed ₹{exp:,.2f} (difference ₹{diff:+,.2f}).",
            amount_at_stake=abs(diff),
            detail={"gst_charged": invoice["gst_amount"], "gst_expected": exp, "difference": diff},
        ))

    findings.sort(key=lambda f: SEVERITY.index(f.code))
    return findings
