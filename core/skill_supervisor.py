"""Central skill registry, task planner, and DAG executor.

The planner returns only registered skill IDs. Independent skills execute concurrently;
dependencies are respected in waves. Results are written to a shared artifact blackboard.
"""
import asyncio
import json
import os
import re
from typing import Any, Dict, List

from core.skill_loader import skill_registry
from core.llm_router import router

SKILL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "instagram-agent-skill": {"department": "content", "description": "Instagram reels, hooks, captions, hashtags and campaign content.", "keywords": r"instagram|reel|caption|hashtag"},
    "youtube-agent-skill": {"department": "content", "description": "YouTube scripts, titles, thumbnail concepts and retention.", "keywords": r"youtube|video script|thumbnail|video"},
    "linkedin-agent-skill": {"department": "content", "description": "LinkedIn posts, profile positioning, carousels and professional outreach.", "keywords": r"linkedin|professional post"},
    "x-agent-skill": {"department": "content", "description": "X/Twitter posts, threads and social hooks.", "keywords": r"twitter|\bx\b|thread"},
    "founder-skill": {"department": "strategy", "description": "Startup strategy, product validation, go-to-market and unit economics.", "keywords": r"startup|founder|business plan|validate|strategy"},
    "trader-skill": {"department": "strategy", "description": "Market and portfolio analysis with explicit assumptions and risk caveats.", "keywords": r"trading|portfolio|stock|market analysis|investment"},
    "replica-skill": {"department": "engineering", "description": "Software architecture, implementation plans, code and product parity.", "keywords": r"code|coding|build|develop|web app|mobile app|api|debug|software|repository|github|deploy"},
    "arena-skill": {"department": "engineering", "description": "Review complex engineering solutions, compare approaches and identify defects.", "keywords": r"complex code|review code|code tournament|architecture|debug"},
    "master-skills": {"department": "strategy", "description": "Coordinate cross-functional plans, video retention, and full-stack work.", "keywords": r"coordinate|full.?stack|master plan"},
    "google-maps-scraper-kit": {"department": "growth", "description": "Collect local business leads from a configured Google Maps scraper service; never fabricate records.", "keywords": r"scrape|google maps|local businesses|business leads|companies in|leads"},
    "sales-desk-skill": {"department": "growth", "description": "Personalized B2B outreach, cold emails and follow-up sequences from supplied leads.", "keywords": r"cold email|outreach|sales|lead generation|prospect"},
    "humanizer-core-skill": {"department": "content", "description": "Improve naturalness and clarity without changing facts, identifiers or data.", "keywords": r"humanize|natural wording|human-like"},
    "seo-agent-skill": {"department": "growth", "description": "SEO intent, keyword clusters, on-page recommendations and competitor analysis.", "keywords": r"seo|keyword|search ranking|organic traffic"},
    "browser-agent-skill": {"department": "workspace", "description": "Plan or perform browser workflows using connected browser tools; state clearly when a tool is unavailable.", "keywords": r"website|browse|browser|latest news|open website|scrape website|visit site"},
    "opendots-coworker-skill": {"department": "workspace", "description": "Break long-running workspace tasks into operational steps and use configured coworker tools.", "keywords": r"autonomous|coworker|long.running|shell|docker|workspace"},
}

# A dependency edge means the prerequisite must finish before the dependent skill starts.
DEPENDENCIES = {
    "browser-agent-skill": {"google-maps-scraper-kit"},
    "sales-desk-skill": {"google-maps-scraper-kit", "browser-agent-skill"},
    "humanizer-core-skill": {"sales-desk-skill", "instagram-agent-skill", "youtube-agent-skill", "linkedin-agent-skill", "x-agent-skill"},
}

DEPARTMENT_NODES = {
    "content": "branch_b_content",
    "growth": "branch_a_sales",
    "strategy": "branch_d_coworker",
    "engineering": "branch_c_tech",
    "workspace": "branch_d_coworker",
}


def deterministic_skill_plan(query: str) -> List[str]:
    """Return relevant skills in dependency-safe order; safe fallback is the master skill."""
    text = (query or "").strip()
    if not text:
        return ["master-skills"]
    selected = [
        skill_id for skill_id, meta in SKILL_REGISTRY.items()
        if re.search(meta["keywords"], text, re.I)
    ]
    if not selected:
        selected = ["master-skills"]
    # If a lead-sourcing task requests outreach or website research, include its prerequisites.
    if "sales-desk-skill" in selected and re.search(r"scrape|google maps|companies in|business leads|latest news|website", text, re.I):
        selected.extend(["google-maps-scraper-kit", "browser-agent-skill"])
    if "browser-agent-skill" in selected and re.search(r"scrape|google maps|companies in|business leads", text, re.I):
        selected.append("google-maps-scraper-kit")
    # Preserve registry order and add prerequisites before dependent nodes.
    wanted = set(selected)
    changed = True
    while changed:
        changed = False
        for node in tuple(wanted):
            for prerequisite in DEPENDENCIES.get(node, set()):
                if prerequisite not in wanted:
                    wanted.add(prerequisite)
                    changed = True
    ordered = [skill_id for skill_id in SKILL_REGISTRY if skill_id in wanted]
    # Return a dependency-safe sequence; each wave may still execute concurrently.
    return [skill_id for wave in _ready_waves(ordered) for skill_id in wave]


def _parse_plan(raw: str) -> List[str]:
    try:
        match = re.search(r"\{[\s\S]*\}", raw)
        payload = json.loads(match.group(0)) if match else {}
        selected = payload.get("selected_skills", [])
        if not isinstance(selected, list):
            return []
        return list(dict.fromkeys(s for s in selected if isinstance(s, str) and s in SKILL_REGISTRY))
    except (ValueError, TypeError, json.JSONDecodeError):
        return []


async def plan_skills(query: str) -> Dict[str, Any]:
    """LLM-assisted planning with deterministic fallback and strict registry validation."""
    fallback = deterministic_skill_plan(query)
    descriptions = "\n".join(f"- {key}: {value['description']}" for key, value in SKILL_REGISTRY.items())
    prompt = (
        "You are a supervisor planning a natural-language task for specialized workers. "
        "Select only necessary registered skills, in execution order. Include dependencies when "
        "needed; independent skills may later run in parallel. Never claim tools or data sources exist "
        "unless configured. Return JSON: {\"selected_skills\":[skill IDs],\"reasoning\":\"brief reason\"}.\n"
        f"Registered skills:\n{descriptions}\nUser task: {query}"
    )
    try:
        raw = await router.generate_tier1(prompt)
        selected = _parse_plan(raw)
        if not selected:
            selected = fallback
        return {"selected_skills": selected, "reasoning": "LLM plan validated against registry."}
    except Exception:
        return {"selected_skills": fallback, "reasoning": "Deterministic intent plan used because the planning model was unavailable."}


def _ready_waves(selected: List[str]) -> List[List[str]]:
    """Topologically group selected skills into parallel execution waves."""
    pending = set(selected)
    done = set()
    waves: List[List[str]] = []
    while pending:
        ready = [
            skill for skill in SKILL_REGISTRY
            if skill in pending and DEPENDENCIES.get(skill, set()).intersection(pending) == set()
        ]
        if not ready:
            # Invalid/cyclic dependencies must fail closed rather than hang.
            raise ValueError(f"Skill dependency cycle or invalid plan: {sorted(pending)}")
        waves.append(ready)
        done.update(ready)
        pending.difference_update(ready)
    return waves


async def execute_skill_plan(query: str, selected_skills: List[str] | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Execute skill definitions in parallel waves and return a shared blackboard artifact map."""
    selected = list(dict.fromkeys(s for s in (selected_skills or deterministic_skill_plan(query)) if s in SKILL_REGISTRY))
    if not selected:
        selected = ["master-skills"]
    artifacts: Dict[str, Any] = {"original_request": query, "skills": {}, "execution_waves": []}
    shared_context = dict(context or {})
    for wave in _ready_waves(selected):
        artifacts["execution_waves"].append(wave)
        prior = json.dumps(artifacts["skills"], ensure_ascii=False, default=str)[:16000]

        async def run_one(skill_id: str) -> tuple[str, str]:
            meta = SKILL_REGISTRY[skill_id]
            task = (
                f"Complete your assigned portion of this user request: {query}\n"
                f"Department: {meta['department']}\nSpecific responsibility: {meta['description']}\n"
                "Use available context and earlier blackboard artifacts. Be concrete. "
                "Do not invent scraped records, news, metrics, tool execution, or completed external actions. "
                "If an external connector/service is unavailable, clearly label the limitation and provide a useful next step."
            )
            worker_context = {**shared_context, "blackboard_artifacts": artifacts["skills"], "prior_artifacts_json": prior}

            if skill_id == "google-maps-scraper-kit":
                from workers.maps_scraper_worker import MapsScraperWorker
                target_prompt = (
                    "Extract a city and business category from this request. Return only JSON "
                    '{"city":"...","category":"..."}. If either is unclear, use an empty string. '
                    f"Request: {query}"
                )
                city, category = "", ""
                try:
                    target_raw = await router.generate_tier1(target_prompt)
                    target_match = re.search(r"\\{[\\s\\S]*\\}", target_raw)
                    target = json.loads(target_match.group(0)) if target_match else {}
                    city = str(target.get("city", "")).strip()
                    category = str(target.get("category", "")).strip()
                except Exception:
                    pass
                if not city:
                    city_match = re.search(r"\\b(?:in|from|of)\\s+([A-Z][A-Za-z]+(?:\\s+[A-Z][A-Za-z]+){0,2})", query)
                    hindi_match = re.search(r"\\b([A-Z][A-Za-z]+)\\s+ke\\b", query, re.I)
                    city = (city_match or hindi_match).group(1) if (city_match or hindi_match) else ""
                if not category:
                    category_match = re.search(r"\\b(IT companies|software companies|restaurants|hotels|hospitals|schools|colleges|real estate agencies|manufacturers|law firms)\\b", query, re.I)
                    category = category_match.group(1) if category_match else ""
                if not city or not category:
                    return skill_id, "Scraper not run: city or business category could not be reliably extracted. Please include both."
                csv_result = await MapsScraperWorker().scrape_leads(city, category)
                return skill_id, f"Target: {category} in {city}\\n{csv_result}"

            if skill_id == "browser-agent-skill":
                if not os.getenv("OPENAI_API_KEY"):
                    return skill_id, "Browser execution unavailable: set OPENAI_API_KEY for browser-use's vision model. No website was opened."
                from skills.browser_agent import run_browser_task
                browser_task = (
                    f"Research this request using read-only browser actions where possible: {query}. "
                    "Return the URLs visited, current factual findings, and any uncertainty. "
                    "Do not submit forms, send messages, purchase items, or make irreversible changes."
                )
                browser_result = await asyncio.to_thread(
                    run_browser_task.invoke,
                    {"task": browser_task, "context": worker_context, "headless": True},
                )
                return skill_id, str(browser_result)

            result = await skill_registry.execute_skill(skill_id, task, context=worker_context)
            return skill_id, result

        results = await asyncio.gather(*(run_one(skill_id) for skill_id in wave), return_exceptions=True)
        for skill_id, result in zip(wave, results):
            if isinstance(result, Exception):
                artifacts["skills"][skill_id] = {"status": "failed", "error": str(result)}
            else:
                _, output = result
                artifacts["skills"][skill_id] = {"status": "completed", "output": output}
    return artifacts
