"""Queue worker helpers for executing queued agent tasks with bounded retries."""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from core.task_queue import BlackboardTaskQueue, QueuedTask, task_queue

logger = logging.getLogger(__name__)
TaskHandler = Callable[[QueuedTask], Awaitable[Any]]


async def run_worker(
    handler: TaskHandler,
    queue: BlackboardTaskQueue = task_queue,
    max_attempts: int = 3,
) -> None:
    """Continuously consume tasks; retry transient failures and always ack queue items."""
    while True:
        task = await queue.dequeue()
        try:
            await handler(task)
        except asyncio.CancelledError:
            # Requeue before propagating shutdown cancellation.
            await queue.retry(task, max_attempts=max_attempts)
            raise
        except Exception:
            logger.exception("Agent task %s failed (attempt %s)", task.task_id, task.attempts + 1)
            await queue.retry(task, max_attempts=max_attempts)
        else:
            await queue.complete(task)
        finally:
            queue.task_done()


async def execute_skill_task(task: QueuedTask) -> Dict[str, Any]:
    """Default handler for skill tasks; task payload carries skill name and task text."""
    from core.skill_loader import skill_registry

    skill_name = str(task.payload.get("skill_name", ""))
    prompt = str(task.payload.get("task", ""))
    if not skill_name or not prompt:
        raise ValueError("skill_name and task are required in queued task payload")
    result = await skill_registry.execute_skill(
        skill_name, prompt, context=task.payload.get("context") or {}
    )
    return {"mission_id": task.mission_id, "agent": task.agent, "result": result}
