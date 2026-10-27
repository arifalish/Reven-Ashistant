import re

with open('core/orchestrator_graph.py', 'r') as f:
    content = f.read()

# Replace ingestion logic with dynamic supervisor
new_ingestion = """from core.supervisor_router import analyze_task_and_route

async def node_supervisor(state: BlackboardState) -> Dict:
    \"\"\"Phase 1: Dynamic Supervisor & Routing\"\"\"

    # 1. Decide routing
    next_nodes = await analyze_task_and_route(state.raw_thought)

    # 2. If it's just a general chat, generate response immediately
    general_response = ""
    if "general_chat" in next_nodes:
        prompt = f"Answer the following query clearly and concisely:\\n{state.raw_thought}"
        general_response = await router.generate_tier1(prompt)
    else:
        # Otherwise generate a master strategy to feed the agents
        strategy_prompt = f"Analyze business thought: {state.raw_thought}. Provide a brief master strategy for the agents."
        strategy = await router.generate_tier1(strategy_prompt)
        state.founder_strategy = {"summary": strategy}

    return {
        "next_nodes": next_nodes,
        "general_response": general_response,
        "founder_strategy": state.founder_strategy
    }

async def node_hitl_gate(state: BlackboardState) -> Dict:
    \"\"\"Phase 2: Human-in-the-Loop Gateway\"\"\"
    if "general_chat" in state.next_nodes:
        # No approval needed for general chat
        return {}

    # Check if user has already provided approval/edits
    if "(Edit:" in state.raw_thought:
        return {}

    # Pause execution for approval
    _ = interrupt("Please approve the strategy via Telegram callback.")
    return {}

def check_supervisor_routing(state: BlackboardState):
    \"\"\"Route to appropriate nodes based on supervisor decision.\"\"\"
    if "general_chat" in state.next_nodes:
        return ["general_chat_node"]

    if "(Edit:" in state.raw_thought:
        return ["supervisor"]

    # Launch approved branches in parallel
    valid_branches = [n for n in state.next_nodes if n != "general_chat"]
    return valid_branches

async def node_general_chat(state: BlackboardState) -> Dict:
    \"\"\"Handles general conversational queries.\"\"\"
    return {"final_report": state.general_response}
"""

content = re.sub(r'from core.supervisor_router import analyze_task_and_route.*?def check_hitl_routing.*?(?=async def node_branch_a_sales)', lambda m: new_ingestion, content, flags=re.DOTALL)

# Let's fix the invalid docstrings manually to avoid raw string backslash issues
content = content.replace('\\"\\"\\"', '"""')

with open('core/orchestrator_graph.py', 'w') as f:
    f.write(content)
