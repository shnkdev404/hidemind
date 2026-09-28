"""Learning-curve metrics, computed straight from the audit tables."""

from collections import defaultdict

from sqlmodel import Session, select

from ..models import Decision, ExceptionCase, Invoice, Proposal, TrustCell

APPROVE_ACTIONS = {"APPROVE", "APPROVE_PARTIAL"}


def weekly(s: Session) -> list[dict]:
    cases = s.exec(select(ExceptionCase)).all()
    invoices = {i.id: i for i in s.exec(select(Invoice)).all()}
    decisions = {d.case_id: d for d in s.exec(select(Decision)).all()}
    proposals: dict[int, Proposal] = {}
    for p in s.exec(select(Proposal).where(Proposal.mode.in_(["MEMORY", "FALLBACK"])).order_by(Proposal.id)):
        proposals[p.case_id] = p  # latest wins

    rows: dict[int, dict] = defaultdict(lambda: {"exceptions": 0, "auto": 0, "graded": 0, "correct": 0,
                                                 "decided": 0, "agreed": 0, "risk_blocked": 0, "conf_sum": 0.0,
                                                 "n_prop": 0, "invoices": 0})
    for inv in invoices.values():
        rows[inv.week]["invoices"] += 1
    for c in cases:
        r = rows[c.week]
        r["exceptions"] += 1
        p, d = proposals.get(c.id), decisions.get(c.id)
        gt = invoices[c.invoice_id].ground_truth or {}
        if p:
            r["n_prop"] += 1
            r["conf_sum"] += p.confidence
            if gt:
                r["graded"] += 1
                r["correct"] += int(p.action == gt.get("action"))
        if d:
            r["auto"] += int(d.auto)
            if d.agreed_with_agent is not None:
                r["decided"] += 1
                r["agreed"] += int(d.agreed_with_agent)
        if c.primary_code in ("BANK_CHANGE", "DUPLICATE"):
            final = d.action if d else (p.action if p else None)
            r["risk_blocked"] += int(final is not None and final not in APPROVE_ACTIONS)

    out = []
    for week in sorted(rows):
        r = rows[week]
        out.append({
            "week": week, "invoices": r["invoices"], "exceptions": r["exceptions"], "auto_resolved": r["auto"],
            "auto_rate": round(r["auto"] / r["exceptions"], 3) if r["exceptions"] else 0,
            "accuracy": round(r["correct"] / r["graded"], 3) if r["graded"] else None,
            "agreement": round(r["agreed"] / r["decided"], 3) if r["decided"] else None,
            "avg_confidence": round(r["conf_sum"] / r["n_prop"], 3) if r["n_prop"] else None,
            "risk_blocked": r["risk_blocked"],
        })
    return out


def summary(s: Session) -> dict:
    cells = s.exec(select(TrustCell)).all()
    levels = {0: 0, 1: 0, 2: 0}
    for c in cells:
        levels[c.level] = levels.get(c.level, 0) + 1
    weeks = weekly(s)
    return {
        "weeks": weeks,
        "trust_levels": {"intern": levels[0], "associate": levels[1], "senior": levels[2]},
        "total_exceptions": sum(w["exceptions"] for w in weeks),
        "total_auto": sum(w["auto_resolved"] for w in weeks),
        "risk_blocked": sum(w["risk_blocked"] for w in weeks),
    }
