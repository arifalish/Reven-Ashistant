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
    "founder-skill": {"department": "strategy", "description": "Startup strategy, product validation, go-to-market and unit economics.", "keywords": r"startup|founder|business|validate|strategy"},
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

# Each sub-agent is an independently executed LLM worker with a defined responsibility.
# External actions (posting, sending messages, scraping, trading, logging in) still require
# an explicitly configured connector and are never claimed without execution evidence.
SUBAGENT_REGISTRY: Dict[str, List[Dict[str, str]]] = {
    "instagram-agent-skill": [
        {"id":"visual_content_analyst","name":"Visual Content Analyst","task":"Plan/analyze carousel, Reels and post aesthetics, format, visual hierarchy and template brief."},
        {"id":"caption_hook_writer","name":"Caption & Hook Writer","task":"Write high-engagement hooks, captions, CTA and niche-relevant hashtag suggestions."},
        {"id":"dm_comment_responder","name":"DM & Comment Responder","task":"Draft helpful replies to likely user DMs/comments; do not send them without an authorized messaging connector."},
        {"id":"growth_analytics_monitor","name":"Growth & Analytics Monitor","task":"Define reach, impressions, shares, retention/drop-off metrics and experiments; never invent live analytics."},
    ],
    "youtube-agent-skill": [
        {"id":"idea_trend_scout","name":"Idea & Trend Scout","task":"Identify topic angles, audience intent, competitor-format hypotheses and keywords; label live trend data unavailable unless sourced."},
        {"id":"script_architect","name":"Script Architect","task":"Create retention-aware long-form script or Shorts structure with hook, beats and CTA."},
        {"id":"thumbnail_title_optimizer","name":"Thumbnail & Title Optimizer","task":"Generate title variants and a specific thumbnail design brief, optimized as hypotheses not guaranteed CTR."},
        {"id":"seo_metadata_specialist","name":"SEO & Metadata Specialist","task":"Draft description, chapters/timestamps, tags and playlist recommendations."},
    ],
    "linkedin-agent-skill": [
        {"id":"thought_leadership_drafter","name":"Thought Leadership Drafter","task":"Turn supplied insights into a professional post, case study or founder story."},
        {"id":"network_engagement_bot","name":"Network Engagement Bot","task":"Draft relevant, substantive comments; never claim to have visited or commented on posts without browser evidence."},
        {"id":"inmail_outreach_specialist","name":"InMail & Outreach Specialist","task":"Write personalized connection requests and B2B follow-ups using only provided or verified prospect context."},
    ],
    "x-agent-skill": [
        {"id":"thread_architect","name":"Thread Architect","task":"Split the idea into a compelling, coherent X thread with a strong opening and conclusion."},
        {"id":"realtime_trend_monitor","name":"Real-Time Trend Monitor","task":"Identify what current data would be needed for trend validation; do not invent live trends or quote-tweets."},
        {"id":"community_manager","name":"Community Manager","task":"Draft replies and triage mentions by relevance, risk and response priority; do not publish without authorization."},
    ],
    "founder-skill": [
        {"id":"strategy_vision_planner","name":"Strategy & Vision Planner","task":"Validate the business model, roadmap, risks and quarterly OKRs."},
        {"id":"pitch_deck_investor","name":"Pitch Deck & Investor Agent","task":"Draft pitch narrative, executive summary and clearly labelled financial assumptions/projections."},
        {"id":"decision_simulator","name":"Decision Simulator","task":"Compare options, trade-offs, hiring choices and resource allocation scenarios."},
        {"id":"operations_orchestrator","name":"Operations Orchestrator","task":"Prioritize daily/weekly tasks, owners, dependencies and cross-functional workflow."},
    ],
    "trader-skill": [
        {"id":"market_data_fetcher","name":"Market Data Fetcher","task":"Identify required price candles and calculate/interpret RSI, MACD and volume only from supplied or connected data."},
        {"id":"risk_capital_manager","name":"Risk & Capital Manager","task":"Calculate position sizing and stop-loss/risk-reward scenarios from explicit capital and risk inputs; no trade execution."},
        {"id":"backtesting_engine","name":"Backtesting Engine","task":"Specify or run backtest logic only where historical data and an execution environment are available; report assumptions and limitations."},
        {"id":"sentiment_news_analyst","name":"Sentiment & News Analyst","task":"Analyze supplied macro/company news and sentiment; clearly flag when current news sources are unavailable."},
    ],
    "replica-skill": [
        {"id":"persona_tone_profiler","name":"Persona & Tone Profiler","task":"Profile supplied examples for voice, tone, audience and recurring stylistic traits without inventing personal facts."},
        {"id":"style_consistency_enforcer","name":"Style Consistency Enforcer","task":"Apply the defined voice consistently across outputs and flag conflicting style choices."},
        {"id":"context_memory_sync","name":"Context Memory Sync","task":"Summarize relevant supplied context for reuse and distinguish saved facts from assumptions."},
    ],
    "arena-skill": [
        {"id":"multi_model_evaluator","name":"Multi-Model Evaluator","task":"Compare alternative solution approaches. Do not claim GPT/Claude/Gemini/Llama were called unless actual configured connectors were used."},
        {"id":"blind_judge","name":"Blind Judge Agent","task":"Score anonymized candidate outputs on correctness, clarity, logic, completeness and formatting."},
        {"id":"consensus_aggregator","name":"Consensus Aggregator","task":"Synthesize the strongest supported parts and explicitly preserve disagreements/uncertainty."},
    ],
    "master-skills": [
        {"id":"intent_classifier_router","name":"Intent Classifier & Router","task":"Classify the user intent and map it to registered skills and dependencies."},
        {"id":"workflow_orchestrator","name":"Workflow Orchestrator","task":"Plan multi-step workflow, dependencies, parallelizable stages and completion checks."},
        {"id":"quality_error_checker","name":"Quality & Error Checker","task":"Check output against the request, flag unsupported claims and suggest bounded retries."},
    ],
    "google-maps-scraper-kit": [
        {"id":"location_query_parser","name":"Location & Query Parser","task":"Extract business niche, city/area, radius and filters; ask for missing essential location/category."},
        {"id":"data_extraction_agent","name":"Data Extraction Agent","task":"Normalize business records from connected scraper results only; do not fabricate businesses or contact details."},
        {"id":"cleaner_deduplicator","name":"Cleaner & Deduplicator","task":"Deduplicate and normalize records, validate fields and prepare CSV/JSON/CRM-ready output."},
    ],
    "sales-desk-skill": [
        {"id":"lead_qualifier_bant","name":"Lead Qualifier (BANT)","task":"Assess budget, authority, need and timeline from available evidence; mark unknown fields unknown."},
        {"id":"cold_email_personalizer","name":"Cold Email Personalizer","task":"Draft prospect-specific emails using verified company/profile facts and cite personalization evidence."},
        {"id":"objection_handling_bot","name":"Objection Handling Bot","task":"Prepare honest responses to pricing, timing, competitor and trust objections."},
        {"id":"deal_followup_tracker","name":"Deal Closer & Follow-Up Tracker","task":"Propose pipeline stage, next action and follow-up schedule; do not claim reminders were scheduled unless a tool confirms it."},
    ],
    "humanizer-core-skill": [
        {"id":"cadence_tuner","name":"Perplexity & Burstiness Tuner","task":"Vary sentence cadence and vocabulary naturally while preserving meaning and factual content."},
        {"id":"cliche_remover","name":"Cliché Remover","task":"Remove generic clichés, repetitive transitions and robotic phrasing without altering facts."},
        {"id":"quality_verifier","name":"Quality Verification Agent","task":"Check clarity, fidelity, grammar and tone; do not promise detector bypass or claim an external detector score without a real tool."},
    ],
    "seo-agent-skill": [
        {"id":"keyword_serp_analyzer","name":"Keyword & SERP Analyzer","task":"Map search intent and keyword clusters; distinguish hypotheses from live volume/difficulty data."},
        {"id":"onpage_optimizer","name":"On-Page Optimization Agent","task":"Recommend H1/H2/H3, URL, alt text, internal links and title/meta changes."},
        {"id":"content_gap_identifier","name":"Content Gap Identifier","task":"Identify likely missing sections and compare against supplied competitor/ranking content only."},
        {"id":"schema_technical_validator","name":"Schema & Technical Validator","task":"Draft appropriate JSON-LD schema and technical validation checklist."},
    ],
    "browser-agent-skill": [
        {"id":"dom_element_finder","name":"DOM & Element Finder","task":"Identify target page elements/selectors from browser/DOM evidence or propose robust locator strategy."},
        {"id":"action_executor","name":"Action Executor","task":"Prepare or execute only actions supported by configured browser tools; seek approval for irreversible actions."},
        {"id":"visual_verifier","name":"Visual Verification Agent","task":"Verify page state using actual screenshot/tool evidence; otherwise return verification steps."},
        {"id":"session_cookie_manager","name":"Session & Cookie Manager","task":"Diagnose login/session state using authorized tools; never bypass access controls or anti-bot protections."},
    ],
    "opendots-coworker-skill": [
        {"id":"meeting_note_synthesizer","name":"Meeting & Note Synthesizer","task":"Summarize supplied transcripts/chats and extract decisions, owners and action items."},
        {"id":"workspace_document_drafter","name":"Workspace Document Drafter","task":"Draft SOPs, internal memos and project briefs based on available context."},
        {"id":"task_tracking_agent","name":"Task Tracking Agent","task":"Track deliverables, blockers and follow-up recommendations; only create reminders through a configured tool."},
    ],
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
    # Generated content and outreach receive a final quality/humanization pass.
    if "sales-desk-skill" in selected or any(SKILL_REGISTRY[s]["department"] == "content" for s in selected):
        selected.append("humanizer-core-skill")
    # If a lead-sourcing task requests outreach or website research, include its prerequisites.
    if "sales-desk-skill" in selected and re.search(r"scrape|google maps|companies in|business leads|latest news|website", text, re.I):
        selected.extend(["google-maps-scraper-kit", "browser-agent-skill"])
    if "browser-agent-skill" in selected and re.search(r"scrape|google maps|companies in|business leads", text, re.I):
        selected.append("google-maps-scraper-kit")
    # Add only task-relevant prerequisites above; do not expand optional finalizers
    # into every possible upstream skill.
    ordered = [skill_id for skill_id in SKILL_REGISTRY if skill_id in set(selected)]
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
        model_selected = _parse_plan(raw)
        # A confident deterministic match wins. Do not let a broad LLM plan
        # silently add unrelated skills (e.g. Instagram + YouTube for one video).
        # Use model routing only when deterministic routing found no specific skill.
        selected = fallback if fallback != ["master-skills"] else (model_selected or fallback)
        selected = [skill for wave in _ready_waves(selected) for skill in wave]
        return {"selected_skills": selected, "reasoning": "Selected the smallest deterministic skill set matching the request."}
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

            async def execute_specialists(evidence: str) -> List[Dict[str, Any]]:
                roles = SUBAGENT_REGISTRY.get(skill_id, [])
                async def run_role(agent: Dict[str, str]) -> Dict[str, Any]:
                    prompt = (
                        f"Role: {agent['name']}\\nResponsibility: {agent['task']}\\n"
                        f"User request: {query}\\nTool evidence: {evidence[:7000]}\\n"
                        "Return a concrete artifact; do not claim actions beyond the evidence."
                    )
                    try:
                        output = await asyncio.wait_for(router.generate_tier3(prompt), timeout=75)
                        return {"id": agent["id"], "name": agent["name"], "status": "completed", "output": output}
                    except Exception as exc:
                        return {"id": agent["id"], "name": agent["name"], "status": "failed", "error": type(exc).__name__}
                return await asyncio.gather(*(run_role(role) for role in roles))

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
                specialist_results = await execute_specialists(str(csv_result))
                completed = sum(item["status"] == "completed" for item in specialist_results)
                return skill_id, {
                    "status": "completed" if completed else "failed",
                    "output": f"Target: {category} in {city}\\n{csv_result}",
                    "subagents": specialist_results,
                    "subagent_count": len(specialist_results),
                    "subagents_completed": completed,
                }

            if skill_id == "browser-agent-skill":
                if not (os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_API_KEYS")):
                    return skill_id, {"status": "failed", "error": "NVIDIA_API_KEY is not configured; browser task was not run.", "subagents": []}
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
                specialist_results = await execute_specialists(str(browser_result))
                completed = sum(item["status"] == "completed" for item in specialist_results)
                return skill_id, {
                    "status": "completed" if completed else "failed",
                    "output": str(browser_result),
                    "subagents": specialist_results,
                    "subagent_count": len(specialist_results),
                    "subagents_completed": completed,
                }

            # Execute the original skill package first, preserving its tools/workflow.
            # Specialist agents then enrich that real skill artifact; package failures remain visible.
            try:
                base_artifact = await skill_registry.execute_skill(skill_id, task, context=worker_context)
            except Exception as exc:
                return skill_id, {"status": "failed", "error": f"Skill package execution failed: {type(exc).__name__}", "subagents": []}

            # Run every registered sub-agent as a real, bounded model-backed worker.
            # Individual outputs are kept as blackboard artifacts and then synthesized.
            subagents = SUBAGENT_REGISTRY.get(skill_id, [])
            if not subagents:
                result = await skill_registry.execute_skill(skill_id, task, context=worker_context)
                return skill_id, {"status": "completed", "output": result, "subagents": []}

            semaphore = asyncio.Semaphore(4)
            async def run_subagent(agent: Dict[str, str]) -> Dict[str, Any]:
                prompt = (
                    f"You are the {agent['name']} sub-agent for skill {skill_id}.\\n"
                    f"Specialized responsibility: {agent['task']}\\n"
                    f"Original user request: {query}\\n"
                    f"Skill mission: {task}\\n"
                    f"Context and shared blackboard: {json.dumps(worker_context, ensure_ascii=False, default=str)[:9000]}\\n"
                    "Return a concrete artifact for your role. State missing data and tool limitations. "
                    "Never invent live metrics, scraped records, completed actions or sources."
                )
                async with semaphore:
                    try:
                        output = await asyncio.wait_for(router.generate_tier3(prompt), timeout=75)
                        return {"id": agent["id"], "name": agent["name"], "status": "completed", "output": output}
                    except Exception as exc:
                        return {"id": agent["id"], "name": agent["name"], "status": "failed", "error": type(exc).__name__}

            subagent_results = await asyncio.gather(*(run_subagent(agent) for agent in subagents))
            completed = [item for item in subagent_results if item["status"] == "completed"]
            if not completed:
                return skill_id, {"status": "failed", "error": "All registered sub-agents failed", "subagents": subagent_results}
            synthesis_prompt = (
                f"Synthesize these specialist outputs for skill {skill_id}.\\n"
                f"Original request: {query}\\n"
                "Combine complementary findings, resolve contradictions cautiously, preserve useful details, "
                "and explicitly state missing inputs. Do not imply failed sub-agents succeeded.\\n"
                f"Original skill package artifact: {str(base_artifact)[:7000]}\\nSub-agent artifacts: {json.dumps(completed, ensure_ascii=False, default=str)[:18000]}"
            )
            try:
                synthesized = await asyncio.wait_for(router.generate_tier3(synthesis_prompt), timeout=75)
            except Exception:
                synthesized = "\\n\\n".join(f"### {item['name']}\\n{item['output']}" for item in completed)
            return skill_id, {
                "status": "completed",
                "output": synthesized,
                "subagents": subagent_results,
                "subagent_count": len(subagents),
                "subagents_completed": len(completed),
            }

        results = await asyncio.gather(*(run_one(skill_id) for skill_id in wave), return_exceptions=True)
        for skill_id, result in zip(wave, results):
            if isinstance(result, Exception):
                artifacts["skills"][skill_id] = {"status": "failed", "error": str(result)}
            else:
                _, output = result
                if isinstance(output, dict) and "status" in output:
                    artifacts["skills"][skill_id] = output
                else:
                    artifacts["skills"][skill_id] = {"status": "completed", "output": output}
    return artifacts
