"""Central supervisor for natural-language multi-agent routing.

The router combines deterministic intent signals with the configured LLM. This
keeps common tasks routable when the model is unavailable, while allowing
multiple teams to collaborate on compound requests.
"""
import json
import re
from typing import List

from core.llm_router import router

VALID_NODES = {
    "branch_a_sales",
    "branch_b_content",
    "branch_c_tech",
    "branch_d_coworker",
    "general_chat",
}

# Intent patterns are deliberately broad; one message may select several teams.
INTENT_PATTERNS = {
    "branch_a_sales": re.compile(
        r"\b(sales|lead generation|leads|prospect|cold email|outreach|linkedin dm|"
        r"customers?|clients?|b2b|crm|marketing funnel)\b", re.I
    ),
    "branch_b_content": re.compile(
        r"\b(content|youtube|video script|instagram|reel|caption|social media|"
        r"twitter|\bx thread\b|blog|copywriting|post|thumbnail|seo article)\b", re.I
    ),
    "branch_c_tech": re.compile(
        r"\b(code|coding|build|develop|website|web app|mobile app|api|debug|"
        r"bug|software|database|deploy|deployment|architecture|html|javascript|"
        r"python|telegram bot|agent system|repository|github|test suite)\b", re.I
    ),
    "branch_d_coworker": re.compile(
        r"\b(plan|strategy|analy[sz]e|research|compare|workflow|automate|"
        r"project|operations|execute|implement|coordinate|task|business(?: plan| idea)?)\b", re.I
    ),
}

GENERAL_CHAT = re.compile(
    r"^(hi|hello|hey|thanks|thank you|good morning|good evening|how are you)[!.\s]*$",
    re.I,
)


def _deterministic_routes(raw_thought: str) -> List[str]:
    text = (raw_thought or "").strip()
    if not text or GENERAL_CHAT.fullmatch(text):
        return ["general_chat"]

    routes = [node for node, pattern in INTENT_PATTERNS.items() if pattern.search(text)]
    return routes


def _parse_routes(response: str) -> List[str]:
    """Parse and validate a model response without trusting arbitrary node names."""
    try:
        match = re.search(r"\[[\s\S]*?\]", response)
        parsed = json.loads(match.group(0)) if match else []
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return list(dict.fromkeys(item for item in parsed if isinstance(item, str) and item in VALID_NODES))


async def analyze_task_and_route(raw_thought: str) -> List[str]:
    """Select one or more execution branches for a natural-language request."""
    text = (raw_thought or "").strip()
    if not text:
        return ["general_chat"]

    deterministic = _deterministic_routes(text)
    if deterministic == ["general_chat"]:
        return deterministic
    # High-confidence keyword routing is immediate; only fall back to an LLM when
    # no specialist branch can be identified. This avoids an extra model round-trip
    # for ordinary skill requests while preserving multi-branch deterministic routes.
    if deterministic:
        return deterministic

    prompt = f"""You are the centralized supervisor for a multi-agent assistant.
Choose every team needed for the user's complete request. Return ONLY a JSON array
using these exact node names:
- branch_a_sales: B2B sales, lead generation, prospecting, outreach
- branch_b_content: writing, SEO content, video/social posts and campaigns
- branch_c_tech: software, code, websites, APIs, debugging, deployment and technical tasks
- branch_d_coworker: research, planning, analysis, coordination and operational work
- general_chat: simple conversation only, never use with a work task

User message:
{text}

Include multiple teams when the request spans domains. No markdown, no explanation."""
    model_failed = False
    try:
        response = await router.generate_tier1(prompt)
        model_routes = _parse_routes(response)
    except Exception:
        model_routes = []
        model_failed = True

    # Blend model interpretation with high-confidence keyword routes so a weak
    # model response cannot silently drop an obvious requested workstream.
    combined = list(dict.fromkeys(deterministic + [
        node for node in model_routes if node != "general_chat"
    ]))
    if combined:
        return combined
    # Invalid model output should not trigger an unsolicited work mission.
    # A transport/model failure can still use the safe general-work fallback.
    return ["branch_d_coworker"] if model_failed else ["general_chat"]
