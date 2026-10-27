import re
import json
from typing import List
from core.llm_router import router

async def analyze_task_and_route(raw_thought: str) -> List[str]:
    """
    Acts as the intelligent supervisor.
    Analyzes the user's input and determines which specialized skill branches to execute.
    Possible nodes: 'branch_a_sales', 'branch_b_content', 'branch_c_tech', 'branch_d_coworker', 'general_chat'
    """

    prompt = f"""You are the Master Coordinator Supervisor AI.
Analyze the following user task/thought and decide which specialized teams are needed.

Available teams/branches:
- branch_a_sales: For generating B2B leads, cold emails, or LinkedIn DMs.
- branch_b_content: For generating YouTube scripts, Instagram reels, X threads, or social media content.
- branch_c_tech: For generating code, building MVPs, HTML/JS/CSS, or technical architecture.
- branch_d_coworker: For operational analysis, step-by-step reasoning, or general autonomous coworker tasks.
- general_chat: If the user is just asking a simple question, saying hello, or not providing a task that requires agent orchestration.

User Thought: {raw_thought}

Respond ONLY with a valid JSON array of strings containing the exact branch names needed. Do not include markdown formatting or other text.
Example 1: ["branch_a_sales", "branch_c_tech"]
Example 2: ["general_chat"]
Example 3: ["branch_d_coworker", "branch_b_content"]
"""

    try:
        response = await router.generate_tier1(prompt)

        # Try to find JSON array in the response
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                nodes = json.loads(match.group(0))
            except json.JSONDecodeError:
                nodes = ["general_chat"]
        else:
            nodes = ["general_chat"]

        if not isinstance(nodes, list):
            nodes = ["general_chat"]

        # Validate nodes
        valid_nodes = {"branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker", "general_chat"}
        nodes = [n for n in nodes if n in valid_nodes]

        if not nodes:
            nodes = ["general_chat"]

        return nodes

    except Exception as e:
        print(f"Supervisor routing failed: {e}")
        # Default to general chat on failure
        return ["general_chat"]
