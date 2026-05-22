import asyncio
import threading
import time
from collections import defaultdict


class TrainingEventHub:
    def __init__(self):
        self._lock = threading.Lock()
        self._history = defaultdict(list)
        self._subscribers = defaultdict(list)

    def publish(self, job_id: str, event: dict):
        payload = {
            'job_id': job_id,
            'timestamp': time.time(),
            **event,
        }
        with self._lock:
            history = self._history[job_id]
            history.append(payload)
            if len(history) > 200:
                del history[:-200]
            subscribers = list(self._subscribers[job_id])
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, payload)
            except RuntimeError:
                continue

    def history(self, job_id: str) -> list[dict]:
        with self._lock:
            return list(self._history.get(job_id, []))

    def subscribe(self, job_id: str, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers[job_id].append((loop, queue))
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        with self._lock:
            subscribers = self._subscribers.get(job_id, [])
            self._subscribers[job_id] = [item for item in subscribers if item[1] is not queue]


training_event_hub = TrainingEventHub()
