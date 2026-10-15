"""In-memory fan-out of live run events to SSE subscribers.

Events are ALSO stored in the database, so a browser that connects late (or reconnects) first
replays the stored ones and then follows the live stream. This broker only handles the "live" part.
"""

import asyncio
from collections import defaultdict


class RunEvents:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._finished: set[str] = set()

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        if queue in self._subscribers.get(run_id, []):
            self._subscribers[run_id].remove(queue)

    def publish(self, run_id: str, event: dict) -> None:
        for queue in self._subscribers.get(run_id, []):
            queue.put_nowait(event)

    def finish(self, run_id: str) -> None:
        self._finished.add(run_id)
        self.publish(run_id, {"type": "end"})

    def is_finished(self, run_id: str) -> bool:
        return run_id in self._finished


run_events = RunEvents()
