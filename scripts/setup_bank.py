"""Create (or update) the Hindsight bank: mission, disposition, directives, mental models.

Also resets the local database to week 0 and saves the 'week0' demo snapshot.

Usage: python scripts/setup_bank.py [--fresh]   (--fresh deletes the bank first)
"""

import argparse
import asyncio
import json

import _common  # noqa: F401

from app.config import SEED_DIR, get_settings
from app.db import init_db, reset_db
from app.services import snapshots
from app.services.memory import DIRECTIVES, memory


async def main(fresh: bool):
    s = get_settings()
    if not s.memory_enabled:
        raise SystemExit("HINDSIGHT_URL is not set - copy .env.example to .env and fill it in.")
    vendors = json.loads((SEED_DIR / "vendors.json").read_text(encoding="utf-8"))

    print(f"Hindsight: {s.hindsight_url}  bank: {s.bank_id}")
    if fresh:
        print("Deleting existing bank...")
        await memory.delete_bank()
    await memory.setup_bank(vendors)
    print(f"  bank configured, {len(DIRECTIVES)} directives, {len(vendors) + 2} mental models")

    init_db()
    reset_db()
    print("  local database reset to week 0")
    await snapshots.save("week0")
    print("  snapshot 'week0' saved")

    # Smoke test: one retain + recall round trip on a scratch document.
    await memory.retain("Smoke test: Munshi setup completed.", document_id="setup-smoke-test",
                        context="system", tags=["system"], wait=True)
    res = await memory.recall_precedents("Munshi setup", "V00", "NONE", None)
    print(f"  smoke test OK - recall returned {len(res)} result(s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    asyncio.run(main(ap.parse_args().fresh))
