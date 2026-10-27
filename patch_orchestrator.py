import re

with open('core/orchestrator_graph.py', 'r') as f:
    content = f.read()

# Add import for run_opendots_worker
if "from skills.opendots_agent import run_opendots_worker" not in content:
    content = content.replace("from core.llm_router import router\n", "from core.llm_router import router\nfrom skills.opendots_agent import run_opendots_worker\n")

# Add node_branch_d_coworker
new_node = """async def node_branch_d_coworker(state: BlackboardState) -> Dict:
    \"\"\"Phase 3 - Branch D: OpenDots Coworker\"\"\"

    # We dynamically parse the task for the coworker from the user's thought, or provide a generic one.
    coworker_task = f"Analyze the following strategy and suggest operational next steps: {state.founder_strategy.get('summary', '')}"

    # Create ToolNode and invoke
    tool_node = ToolNode([run_opendots_worker])
    from langchain_core.messages import AIMessage
    msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "run_opendots_worker",
            "args": {"task": coworker_task, "context": {"raw_thought": state.raw_thought}},
            "id": "call_opendots_123"
        }]
    )

    res = await tool_node.ainvoke({"messages": [msg]})
    log_output = res["messages"][-1].content

    return {"opendots_log": log_output}

async def node_aggregator"""

content = content.replace("async def node_aggregator", new_node)

# Add node to workflow
if 'workflow.add_node("branch_d_coworker", node_branch_d_coworker)' not in content:
    content = content.replace(
        'workflow.add_node("branch_c_tech", node_branch_c_tech)',
        'workflow.add_node("branch_c_tech", node_branch_c_tech)\nworkflow.add_node("branch_d_coworker", node_branch_d_coworker)'
    )

# Add edges to workflow
if 'workflow.add_edge("hitl_gate", "branch_d_coworker")' not in content:
    content = content.replace(
        'workflow.add_edge("hitl_gate", "branch_c_tech")',
        'workflow.add_edge("hitl_gate", "branch_c_tech")\nworkflow.add_edge("hitl_gate", "branch_d_coworker")'
    )

if 'workflow.add_edge("branch_d_coworker", "aggregator")' not in content:
    content = content.replace(
        'workflow.add_edge("branch_c_tech", "aggregator")',
        'workflow.add_edge("branch_c_tech", "aggregator")\nworkflow.add_edge("branch_d_coworker", "aggregator")'
    )

# Add to final artifacts
if '"08_OpenDots_Coworker_Log.md": state.opendots_log' not in content:
    content = content.replace(
        '"07_Replica_MVP_Codebase": state.replica_codebase',
        '"07_Replica_MVP_Codebase": state.replica_codebase,\n        "08_OpenDots_Coworker_Log.md": state.opendots_log'
    )

with open('core/orchestrator_graph.py', 'w') as f:
    f.write(content)
