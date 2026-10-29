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


@pytest.mark.asyncio
async def test_approval_card_contains_risk_and_scope(monkeypatch):
    state = BlackboardState(
        mission_id="approval-card-test",
        chat_id=101,
        raw_thought="Deploy to production and publish the release",
        selected_skills=["browser-agent-skill"],
        next_nodes=["skill_swarm_node"],
    )
    captured = {}
    def fake_interrupt(payload):
        captured.update(payload)
        return {"action": "approve", "mission_id": "approval-card-test"}
    monkeypatch.setattr("core.orchestrator_graph.interrupt", fake_interrupt)

    update = await node_hitl_gate(state)

    assert captured["type"] == "HITL_APPROVAL_REQUIRED"
    assert captured["risk_level"] == "high"
    assert "deployment" in captured["risk_signals"]
    assert captured["approval_scope"]
    assert update["hitl_decision"]["action"] == "approve"


@pytest.mark.asyncio
async def test_unknown_hitl_decision_fails_closed(monkeypatch):
    state = BlackboardState(
        mission_id="bad-decision-test",
        chat_id=101,
        raw_thought="Delete the old records",
        next_nodes=["skill_swarm_node"],
    )
    monkeypatch.setattr("core.orchestrator_graph.interrupt", lambda _payload: {"action": "maybe"})
    update = await node_hitl_gate(state)
    assert update["next_nodes"] == ["cancelled"]
    assert "blocked" in update["final_report"].lower()


@pytest.mark.asyncio
async def test_edit_requires_fresh_approval(monkeypatch):
    state = BlackboardState(
        mission_id="edit-test",
        chat_id=101,
        raw_thought="Build a website",
        next_nodes=["skill_swarm_node"],
    )
    monkeypatch.setattr("core.orchestrator_graph.interrupt", lambda _payload: {"action": "edit"})
    update = await node_hitl_gate(state)
    assert update["next_nodes"] == ["cancelled"]
    assert "fresh approval" in update["final_report"].lower()


def test_hitl_risk_classifier_marks_destructive_as_critical():
    from core.orchestrator_graph import _classify_hitl_risk
    state = BlackboardState(raw_thought="Delete the production database permanently")
    result = _classify_hitl_risk(state)
    assert result["risk_level"] == "critical"
    assert "destructive" in result["risk_signals"]
