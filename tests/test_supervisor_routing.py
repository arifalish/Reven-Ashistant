import pytest

from core.supervisor_router import _deterministic_routes, _parse_routes


def test_routes_compound_software_and_content_request():
    routes = _deterministic_routes("Build a Telegram bot and write Instagram content for launch")
    assert "branch_c_tech" in routes
    assert "branch_b_content" in routes


def test_routes_sales_and_research_request():
    routes = _deterministic_routes("Find B2B leads and prepare cold email outreach")
    assert "branch_a_sales" in routes


def test_greeting_is_general_chat():
    assert _deterministic_routes("Hello!") == ["general_chat"]


def test_parse_routes_rejects_unknown_nodes():
    assert _parse_routes('["branch_c_tech", "not_a_node", "branch_b_content"]') == [
        "branch_c_tech", "branch_b_content"
    ]


@pytest.mark.asyncio
async def test_queue_priority_deduplication_and_completion():
    from core.task_queue import BlackboardTaskQueue

    queue = BlackboardTaskQueue()
    await queue.enqueue("mission-1", "content", {"text": "later"}, priority=20, task_id="task-later")
    await queue.enqueue("mission-1", "tech", {"text": "urgent"}, priority=1, task_id="task-urgent")
    # Duplicate task IDs are idempotent and do not create extra queue entries.
    await queue.enqueue("mission-1", "tech", {"text": "duplicate"}, priority=1, task_id="task-urgent")
    assert queue.qsize() == 2

    first = await queue.dequeue()
    assert first.task_id == "task-urgent"
    await queue.complete(first)
    queue.task_done()

    second = await queue.dequeue()
    assert second.task_id == "task-later"
    await queue.complete(second)
    queue.task_done()
    await queue.join()
