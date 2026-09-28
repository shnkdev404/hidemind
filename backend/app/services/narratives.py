"""Turn structured AP events into natural-language text (Hindsight extraction works best on prose)."""

from datetime import date

from .matching import EXCEPTION_LABELS


def inr(x: float | None) -> str:
    if x is None:
        return "-"
    neg, x = x < 0, abs(x)
    whole, frac = f"{x:.2f}".split(".")
    if len(whole) > 3:  # Indian grouping: 12,34,567
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if neg else ''}₹{whole}" + ("" if frac == "00" else f".{frac}")


def fmt_date(d: date | str) -> str:
    d = d if isinstance(d, date) else date.fromisoformat(str(d))
    return d.strftime("%d %b %Y")


def case_brief(invoice: dict, vendor: dict, findings: list[dict], po: dict | None, grn: dict | None) -> str:
    """Neutral description of the case, used as the query for reflect and for the amnesia baseline."""
    lines = [
        f"Vendor: {vendor['name']} ({vendor['city']}){' - registered MSME' if vendor.get('msme') else ''}.",
        f"Invoice {invoice['invoice_no']} dated {fmt_date(invoice['invoice_date'])}, "
        f"PO ref {invoice.get('po_ref') or 'none'}, goods {inr(invoice['subtotal'])}, "
        f"GST {inr(invoice['gst_amount'])}, total {inr(invoice['total'])}.",
        f"Submitted by email from {invoice['sender_email']}.",
        "Exceptions detected by the matching engine:",
    ]
    for f in findings:
        lines.append(f"- [{f['code']}] {EXCEPTION_LABELS.get(f['code'], f['code'])}: {f['summary']}")
    if grn:
        lines.append(f"Goods receipt {grn['id']} dated {fmt_date(grn['received_date'])}.")
    return "\n".join(lines)


def case_memory(invoice: dict, vendor: dict, findings: list[dict], proposal: dict | None,
                decision: dict) -> str:
    """The memory we retain once a case is resolved: what happened, what Munshi said, what humans decided and why."""
    codes = ", ".join(EXCEPTION_LABELS.get(f["code"], f["code"]) for f in findings)
    parts = [
        f"On {fmt_date(decision['business_date'])}, invoice {invoice['invoice_no']} from {vendor['name']} "
        f"({inr(invoice['total'])}, PO {invoice.get('po_ref') or 'none'}) was flagged for: {codes}.",
    ]
    for f in findings:
        parts.append(f"Detail: {f['summary']}")
    if proposal:
        parts.append(
            f"Munshi recommended {proposal['action']} with confidence {proposal['confidence']:.2f}."
        )
    if decision.get("auto"):
        parts.append(
            f"Munshi auto-resolved it as {decision['action']}; {decision['decided_by']} reviewed the daily digest "
            f"and {'confirmed' if decision.get('agreed_with_agent') else 'reversed'} it."
        )
    else:
        amt = f" for {inr(decision['approved_amount'])}" if decision.get("approved_amount") else ""
        parts.append(f"{decision['decided_by']} ({decision.get('role') or 'AP team'}) decided {decision['action']}{amt}.")
    if decision.get("reason"):
        parts.append(f"Reason given: \"{decision['reason']}\"")
    if proposal and decision.get("agreed_with_agent") is False:
        parts.append(
            f"This overrode Munshi's recommendation of {proposal['action']} - the correct handling for this "
            f"situation with {vendor['name']} is {decision['action']}."
        )
    return " ".join(parts)
