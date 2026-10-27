"""In-process async task queue shared by supervisor/worker orchestration.

This queue is intentionally transport-agnostic. Deployments can replace it with
Redis/Celery without changing the task envelope or worker contract.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(order=True)
class QueuedTask:
    priority: int
    created_at: float
    task_id: str = field(compare=False)
    mission_id: str = field(compare=False)
    agent: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False, default_factory=dict)
    attempts: int = field(compare=False, default=0)


class BlackboardTaskQueue:
    """Priority queue with duplicate protection and bounded retry support."""

    def __init__(self, maxsize: int = 500):
        self._queue: asyncio.PriorityQueue[QueuedTask] = asyncio.PriorityQueue(maxsize=maxsize)
        self._known: set[str] = set()
        self._lock = asyncio.Lock()

    async def enqueue(
        self, mission_id: str, agent: str, payload: Dict[str, Any],
        priority: int = 100, task_id: Optional[str] = None
    ) -> str:
        if not mission_id or not agent:
            raise ValueError("mission_id and agent are required")
        identifier = task_id or str(uuid.uuid4())
        async with self._lock:
            if identifier in self._known:
                return identifier
            task = QueuedTask(
                priority=priority, created_at=time.time(), task_id=identifier,
                mission_id=mission_id, agent=agent, payload=dict(payload)
            )
            await self._queue.put(task)
            self._known.add(identifier)
        return identifier

    async def dequeue(self) -> QueuedTask:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    def qsize(self) -> int:
        return self._queue.qsize()

    async def retry(self, task: QueuedTask, max_attempts: int = 3) -> bool:
        if task.attempts + 1 >= max_attempts:
            async with self._lock:
                self._known.discard(task.task_id)
            return False
        task.attempts += 1
        task.created_at = time.time()
        await self._queue.put(task)
        return True

    async def complete(self, task: QueuedTask) -> None:
        async with self._lock:
            self._known.discard(task.task_id)


task_queue = BlackboardTaskQueue()
