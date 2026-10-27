import asyncio
import pytest

from core.skill_loader import SkillRegistry


@pytest.mark.asyncio
async def test_skill_definition_is_executable_via_router(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    skill = root / "demo-skill"
    (skill / "templates").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Demo skill\nReturn a concise checklist.", encoding="utf-8")
    (skill / "templates" / "voice.md").write_text("Clear and practical.", encoding="utf-8")
    registry = SkillRegistry(str(root))

    async def fake_generate(prompt):
        assert "Demo skill" in prompt
        assert "Do the task" in prompt
        return "1. Inspect\n2. Execute"

    monkeypatch.setattr("core.skill_loader.router.generate_tier3", fake_generate)
    assert registry.list_skills() == ["demo-skill"]
    result = await registry.execute_skill("demo-skill", "Do the task")
    assert "Inspect" in result


def test_skill_path_traversal_is_rejected(tmp_path):
    registry = SkillRegistry(str(tmp_path / "skills"))
    with pytest.raises(ValueError):
        registry._get_skill_path("../outside")


@pytest.mark.asyncio
async def test_queue_retries_failed_tasks_with_bounded_attempts():
    from core.task_queue import BlackboardTaskQueue

    queue = BlackboardTaskQueue()
    await queue.enqueue("mission", "worker", {"task": "x"}, task_id="retry-me")
    task = await queue.dequeue()
    assert await queue.retry(task, max_attempts=3) is True
    queue.task_done()

    retried = await queue.dequeue()
    assert retried.attempts == 1
    assert await queue.retry(retried, max_attempts=3) is False
    queue.task_done()
    await queue.join()
