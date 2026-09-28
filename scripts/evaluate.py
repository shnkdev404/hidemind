"""Measure Munshi (with Hindsight memory) vs Amnesia (same LLM, no memory) on the held-out weeks.

Prerequisite: history seeded (scripts/seed_history.py). Processes weeks 13-14 if not done yet, then runs the
amnesia baseline on the same cases and prints a comparison table. Numbers are measured, never invented.

Usage: python scripts/evaluate.py [--json results.json]
"""

import argparse
import asyncio
import json
import statistics

import _common  # noqa: F401
from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import ExceptionCase, Invoice
from app.services import simulator
from app.services.orchestrator import latest_proposal, propose

EVAL_WEEKS = (13, 14)


async def main(out: str | None):
    init_db()
    while simulator.current_week() < max(EVAL_WEEKS):
        w = simulator.current_week() + 1
        print(f"Processing week {w}...")
        await simulator.run_week(w)

    rows = []
    with Session(engine) as s:
        cases = s.exec(select(ExceptionCase).where(ExceptionCase.week.in_(EVAL_WEEKS))).all()
        for c in cases:
            gt = (s.get(Invoice, c.invoice_id).ground_truth or {}).get("action")
            mem = latest_proposal(s, c.id)
            amn = latest_proposal(s, c.id, mode="AMNESIA")
            if amn is None:
                amn, _ = await propose(s, c, mode="AMNESIA")
            rows.append({"case_id": c.id, "vendor": c.vendor_id, "code": c.primary_code, "truth": gt,
                         "munshi": mem.action if mem else None, "munshi_mode": mem.mode if mem else None,
                         "munshi_conf": mem.confidence if mem else None, "munshi_ms": mem.latency_ms if mem else None,
                         "amnesia": amn.action, "amnesia_conf": amn.confidence, "amnesia_ms": amn.latency_ms})

    def score(key: str) -> dict:
        graded = [r for r in rows if r["truth"] and r[key]]
        correct = [r for r in graded if r[key] == r["truth"]]
        confident = [r for r in graded if (r[f"{key}_conf"] or 0) >= 0.85 and r[key] == r["truth"]]
        return {"accuracy": len(correct) / len(graded) if graded else 0, "n": len(graded),
                "confident_correct": len(confident) / len(graded) if graded else 0,
                "median_ms": statistics.median([r[f"{key}_ms"] for r in graded]) if graded else 0}

    m, a = score("munshi"), score("amnesia")
    print(f"\nHeld-out weeks {EVAL_WEEKS}: {len(rows)} exception cases\n")
    print(f"{'Metric':<40}{'Amnesia (LLM only)':>20}{'Munshi (Hindsight)':>22}")
    print(f"{'Decision accuracy':<40}{a['accuracy'] * 100:>19.1f}%{m['accuracy'] * 100:>21.1f}%")
    print(f"{'Confident & correct (conf >= 0.85)':<40}{a['confident_correct'] * 100:>19.1f}%"
          f"{m['confident_correct'] * 100:>21.1f}%")
    print(f"{'Median latency':<40}{a['median_ms'] / 1000:>19.1f}s{m['median_ms'] / 1000:>21.1f}s")
    print("\nPer case:")
    for r in rows:
        flag = lambda k: "ok " if r[k] == r["truth"] else "x  "  # noqa: E731
        print(f"  #{r['case_id']:<4}{r['vendor']:<5}{r['code']:<16} truth={r['truth']:<16}"
              f"amnesia={flag('amnesia')}{r['amnesia']:<16} munshi={flag('munshi')}{r['munshi']}")
    if any(r["munshi_mode"] != "MEMORY" for r in rows):
        print("\nNOTE: some Munshi proposals did not use memory (mode FALLBACK) - check Hindsight connectivity.")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"munshi": m, "amnesia": a, "cases": rows}, f, indent=2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    asyncio.run(main(ap.parse_args().json))
