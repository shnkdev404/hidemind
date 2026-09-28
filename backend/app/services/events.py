"""Tiny in-process pub/sub feeding the SSE stream (live toasts in the UI)."""

import asyncio
import json
from typing import Any

_subscribers: set[asyncio.Queue] = set()


def publish(kind: str, **data: Any) -> None:
    msg = json.dumps({"kind": kind, **data}, default=str)
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def subscribe():
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.add(q)
    try:
        while True:
            yield {"data": await q.get()}
    finally:
        _subscribers.discard(q)
