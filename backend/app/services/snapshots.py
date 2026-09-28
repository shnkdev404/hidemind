"""Demo snapshots = SQLite backup file + a server-side clone of the Hindsight bank."""

import sqlite3

from ..config import SNAPSHOT_DIR, get_settings
from ..db import engine
from .memory import memory


def _db_file(name: str):
    return SNAPSHOT_DIR / f"{name}.db"


def list_snapshots() -> list[str]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in SNAPSHOT_DIR.glob("*.db"))


async def save(name: str) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(get_settings().db_path)
    dst = sqlite3.connect(_db_file(name))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    if memory.enabled:
        await memory.snapshot(name)


async def restore(name: str) -> None:
    f = _db_file(name)
    if not f.exists():
        raise FileNotFoundError(f"No snapshot named '{name}'. Available: {list_snapshots()}")
    if memory.enabled:
        await memory.restore(name)
    engine.dispose()
    src = sqlite3.connect(f)
    dst = sqlite3.connect(get_settings().db_path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
