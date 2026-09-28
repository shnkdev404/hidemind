"""Save / restore / list demo snapshots (SQLite file + server-side Hindsight bank clone).

Usage:
  python scripts/snapshot.py list
  python scripts/snapshot.py save week12
  python scripts/snapshot.py restore week12
"""

import asyncio
import sys

import _common  # noqa: F401

from app.db import init_db
from app.services import snapshots


async def main(cmd: str, name: str | None):
    init_db()
    if cmd == "list":
        print("\n".join(snapshots.list_snapshots()) or "(none)")
    elif cmd == "save" and name:
        await snapshots.save(name)
        print(f"saved {name}")
    elif cmd == "restore" and name:
        await snapshots.restore(name)
        print(f"restored {name}")
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "list", sys.argv[2] if len(sys.argv) > 2 else None))
