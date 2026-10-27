import pytest
from core.supervisor_router import analyze_task_and_route
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_analyze_task_and_route():
    with patch("core.supervisor_router.router.generate_tier1", new_callable=AsyncMock) as mock_generate:
        # Test clean JSON
        mock_generate.return_value = '["branch_a_sales"]'
        assert await analyze_task_and_route("test") == ["branch_a_sales"]

        # Test markdown JSON
        mock_generate.return_value = '```json\n["branch_c_tech", "branch_b_content"]\n```'
        assert await analyze_task_and_route("test") == ["branch_c_tech", "branch_b_content"]

        # Test conversational noise
        mock_generate.return_value = 'Here is your JSON:\n["branch_d_coworker"]\nHope this helps!'
        assert await analyze_task_and_route("test") == ["branch_d_coworker"]

        # Test invalid node (fallback to general_chat? actually it filters it out and if empty returns general_chat)
        mock_generate.return_value = '["invalid_node"]'
        assert await analyze_task_and_route("test") == ["general_chat"]

        # Test failure (invalid json array)
        mock_generate.return_value = 'I am just talking'
        assert await analyze_task_and_route("test") == ["general_chat"]
