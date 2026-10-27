import pytest

from core.blackboard_memory import BlackboardState
from core.orchestrator_graph import (
    check_supervisor_routing,
    node_cancelled,
    node_hitl_gate,
)


@pytest.mark.asyncio
async def test_cancel_decision_routes_to_terminal_node(monkeypatch):
    state = BlackboardState(
        mission_id="cancel-test",
        chat_id=101,
        message_id=202,
        raw_thought="Build a website",
        next_nodes=["branch_c_tech"],
    )
    monkeypatch.setattr("core.orchestrator_graph.interrupt", lambda _prompt: {"action": "cancel"})
    update = await node_hitl_gate(state)
    state.next_nodes = update["next_nodes"]
    assert check_supervisor_routing(state) == ["cancelled_node"]
    result = await node_cancelled(state)
    assert "cancelled" in result["final_report"].lower()


def test_supervisor_routes_compound_request_to_multiple_agents():
    state = BlackboardState(
        raw_thought="Build a website and write SEO content",
        next_nodes=["branch_c_tech", "branch_b_content"],
    )
    assert check_supervisor_routing(state) == ["skill_swarm_node"]
