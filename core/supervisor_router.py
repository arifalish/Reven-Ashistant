import json
import re
from typing import List

from core.llm_router import router

SKILL_REGISTRY = [
    "instagram-agent-skill",
    "youtube-agent-skill",
    "linkedin-agent-skill",
    "x-agent-skill",
    "founder-skill",
    "trader-skill",
    "replica-skill",
    "arena-skill",
    "master-skills",
    "google-maps-scraper-kit",
    "sales-desk-skill",
    "humanizer-core-skill",
    "seo-agent-skill",
    "browser-automation-skill",
    "opendots-skill",
    "general_chat",
]


async def analyze_task_and_route(raw_thought: str) -> List[str]:
    """Acts as the intelligent supervisor for the 15-skill swarm."""
    if not raw_thought or not raw_thought.strip():
        return ["general_chat"]

    prompt = f"""You are the Master Coordinator Supervisor AI.
Analyze the following user task and decide which specialized skill agents are required.

Available skills:
- instagram-agent-skill
- youtube-agent-skill
- linkedin-agent-skill
- x-agent-skill
- founder-skill
- trader-skill
- replica-skill
- arena-skill
- master-skills
- google-maps-scraper-kit
- sales-desk-skill
- humanizer-core-skill
- seo-agent-skill
- browser-automation-skill
- opendots-skill
- general_chat

User Thought: {raw_thought}

Respond ONLY with a valid JSON array of strings containing exact skill names needed.
Example: [\"google-maps-scraper-kit\", \"sales-desk-skill\", \"humanizer-core-skill\"]
Example: [\"general_chat\"]
"""

    try:
        response = await router.generate_tier1(prompt)
        match = re.search(r"\[.*\]", response, re.DOTALL)
        nodes = json.loads(match.group(0)) if match else ["general_chat"]
        if not isinstance(nodes, list):
            nodes = ["general_chat"]

        valid = set(SKILL_REGISTRY)
        nodes = [n for n in nodes if n in valid]
        if not nodes:
            nodes = ["general_chat"]
        return nodes
    except Exception:
        # Conservative fallback: if everything fails, do a safe general chat response.
        return ["general_chat"]
