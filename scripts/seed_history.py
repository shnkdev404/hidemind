"""Replay history weeks through the real pipeline (Hindsight + Groq) and save demo snapshots.

Run once before the demo (takes a while: every exception is genuinely triaged and every decision retained).

Usage: python scripts/seed_history.py [--to 12] [--snapshot-every 3]
"""

import argparse
import asyncio
import time

import _common  # noqa: F401

from app.db import init_db
from app.services import simulator, snapshots
from app.services.memory import memory
from app.services.metrics import weekly
from app.db import engine
from sqlmodel import Session


async def main(to_week: int, every: int):
    init_db()
    start = simulator.current_week() + 1
    if start > to_week:
        print(f"Already at week {start - 1}. Reset with scripts/snapshot.py restore week0 first.")
        return
    for w in range(start, to_week + 1):
        t = time.monotonic()
        r = await simulator.run_week(w)
        print(f"week {w:2d}: {r['exceptions']:2d} exceptions, {r['auto_resolved']} auto, "
              f"{r['correct']}/{r['graded']} proposals correct, {r['background_memories']} background "
              f"memories, {time.monotonic() - t:5.1f}s" + (f"  ERRORS: {r['errors']}" if r["errors"] else ""))
        if w % every == 0 or w == to_week:
            await snapshots.save(f"week{w}")
            print(f"         snapshot 'week{w}' saved")

    if memory.enabled:
        print("Refreshing mental models (playbook, fraud watchlist, vendor dossiers)...")
        from app.models import Vendor
        from sqlmodel import select
        with Session(engine) as s:
            ids = [v.id for v in s.exec(select(Vendor)).all()]
        await memory.refresh_all(ids)
        await snapshots.save(f"week{to_week}")

    with Session(engine) as s:
        print("\nLearning curve (proposal accuracy vs the team's actual decisions):")
        for row in weekly(s):
            acc = f"{row['accuracy'] * 100:5.1f}%" if row["accuracy"] is not None else "   - "
            print(f"  week {row['week']:2d}  accuracy {acc}  auto {row['auto_resolved']}/{row['exceptions']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", type=int, default=simulator.HISTORY_WEEKS)
    ap.add_argument("--snapshot-every", type=int, default=3)
    a = ap.parse_args()
    asyncio.run(main(a.to, a.snapshot_every))
