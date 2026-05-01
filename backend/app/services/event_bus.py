"""In-memory event bus for live match SSE broadcasting.

Each match has a set of asyncio.Queue subscribers. When the live poller
detects a change it calls publish(); the SSE generator consumes from its queue.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, Set


class _EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[int, Set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, match_id: int, data: dict) -> None:
        for q in list(self._subscribers.get(match_id, set())):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass  # slow consumer — skip

    def subscribe(self, match_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[match_id].add(q)
        return q

    def unsubscribe(self, match_id: int, q: asyncio.Queue) -> None:
        self._subscribers[match_id].discard(q)
        if not self._subscribers.get(match_id):
            self._subscribers.pop(match_id, None)


# Module-level singleton used by both live_poller and live router
live_event_bus = _EventBus()
