import asyncio
import uuid
import re
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from core.blackboard_memory import BlackboardState, memory_manager
from core.llm_router import router
from skills.opendots_agent import run_opendots_worker
from core.skill_loader import skill_registry
from core.credential_vault import credential_vault
from workers.maps_scraper_worker import scraper_worker
from middleware.quality_humanizer import clean_and_humanize
from skills.browser_agent import run_browser_task

from core.supervisor_router import analyze_task_and_route
from core.skill_supervisor import plan_skills, execute_skill_plan, SKILL_REGISTRY, DEPARTMENT_NODES

async def node_supervisor(state: BlackboardState) -> Dict:
    """Phase 1: Dynamic Supervisor & Routing"""

    # 1. Select exact skill workers, then map their departments for reporting/compatibility.
    next_nodes = await analyze_task_and_route(state.raw_thought)
    if "general_chat" in next_nodes:
        skill_plan = {"selected_skills": [], "reasoning": "General conversation; no specialist worker required."}
    else:
        skill_plan = await plan_skills(state.raw_thought)
    selected_skills = skill_plan["selected_skills"]
    if "general_chat" not in next_nodes:
        selected_departments = list(dict.fromkeys(SKILL_REGISTRY[s]["department"] for s in selected_skills))
        next_nodes = list(dict.fromkeys(
            [DEPARTMENT_NODES[d] for d in selected_departments if d in DEPARTMENT_NODES]
        )) or ["branch_d_coworker"]

    # 2. If it's just a general chat, generate response immediately
    general_response = ""
    if "general_chat" in next_nodes:
        prompt = f"Answer the following query clearly and concisely:\n{state.raw_thought}"
        general_response = await router.generate_tier1(prompt)
    else:
        # Avoid a second blocking LLM round-trip before any worker can start.
        # The skill planner already selected the relevant specialists; pass a
        # deterministic mission brief as shared context instead.
        skill_names = ", ".join(selected_skills) or "general-purpose worker"
        strategy = (
            f"Mission: {state.raw_thought.strip()}\n"
            f"Selected specialists: {skill_names}\n"
            "Execute only the assigned scope, share evidence through the blackboard, "
            "and report blockers instead of claiming unverified external actions."
        )
        state.founder_strategy = {"summary": strategy}

    return {
        "next_nodes": next_nodes,
        "selected_skills": selected_skills,
        "skill_plan_reasoning": skill_plan["reasoning"],
        "general_response": general_response,
        "founder_strategy": state.founder_strategy
    }

async def node_hitl_gate(state: BlackboardState) -> Dict:
    """Phase 2: Human-in-the-Loop Gateway"""
    if "general_chat" in state.next_nodes:
        # No approval needed for general chat
        return {}

    # Check if user has already provided approval/edits
    if "(Edit:" in state.raw_thought:
        return {}

    # Pause execution for explicit approval; preserve cancellation as a graph decision.
    decision = interrupt("Please approve the strategy via Telegram callback.")
    if isinstance(decision, dict) and decision.get("action") == "cancel":
        return {"next_nodes": ["cancelled"]}
    if isinstance(decision, dict) and decision.get("action") not in (None, "approve", "edit"):
        return {"next_nodes": ["cancelled"]}
    return {}

def check_supervisor_routing(state: BlackboardState):
    """Route to appropriate nodes based on supervisor decision."""
    if "cancelled" in state.next_nodes:
        return ["cancelled_node"]
    if "general_chat" in state.next_nodes:
        return ["general_chat_node"]

    if "(Edit:" in state.raw_thought:
        return ["supervisor"]

    # The central skill swarm executes the validated skill DAG; workers are parallelized by wave.
    return ["skill_swarm_node"]

async def node_general_chat(state: BlackboardState) -> Dict:
    """Handles general conversational queries."""
    return {"final_report": state.general_response}

async def node_cancelled(state: BlackboardState) -> Dict:
    """Terminate a mission after an explicit user cancellation."""
    return {"final_report": "Mission cancelled by user. No agent branches were executed."}
async def node_branch_a_sales(state: BlackboardState) -> Dict:
    """Execute sales, lead and LinkedIn skills for a sales task."""
    strategy = state.founder_strategy.get("summary", "")
    try:
        leads = await scraper_worker.scrape_leads("Target City", "Niche")
    except Exception as exc:
        leads = f"Lead scraper unavailable: {exc}"
    context = {"strategy": strategy, "leads": leads[:1000], "raw_request": state.raw_thought}
    emails, linkedin = await asyncio.gather(
        skill_registry.execute_skill("sales-desk-skill", "Prepare B2B outreach for the request.", context),
        skill_registry.execute_skill("linkedin-agent-skill", "Prepare personalized LinkedIn outreach.", context),
    )
    return {"leads_csv": leads, "b2b_emails": [emails, linkedin]}

async def node_branch_b_content(state: BlackboardState) -> Dict:
    """Execute YouTube, Instagram, X and SEO skill handlers in parallel."""
    strategy = state.founder_strategy.get("summary", "")
    context = {"strategy": strategy, "raw_request": state.raw_thought}
    yt_prompt = "Create a YouTube script, title, hook and thumbnail concepts."
    ig_prompt = "Create Instagram Reels hooks, captions and a call to action."
    x_prompt = "Create a concise, engaging X/Twitter thread."
    seo_prompt = "Identify SEO intent and propose optimized content and keywords."

    results = await asyncio.gather(
        skill_registry.execute_skill("youtube-agent-skill", yt_prompt, context),
        skill_registry.execute_skill("instagram-agent-skill", ig_prompt, context),
        skill_registry.execute_skill("x-agent-skill", x_prompt, context),
        skill_registry.execute_skill("seo-agent-skill", seo_prompt, context),
    )
    results = results[:3]


    # Dynamic LLM routing to the browser tool if requested by the user
    # Binds the LangChain tool and parses it into a ToolNode equivalent output
    if "post to twitter" in state.raw_thought.lower() or "open browser" in state.raw_thought.lower():
        browser_plan = await skill_registry.execute_skill(
            "browser-agent-skill",
            "Create a safe browser execution checklist for the requested action. Do not claim the action was performed.",
            {"raw_request": state.raw_thought, "draft_content": results[2]},
        )
        tool_node = ToolNode([run_browser_task])
        # We manually invoke the node here inside the branch for demonstration.
        # In a real expanded graph, this would be its own standalone node edge.
        from langchain_core.messages import AIMessage
        msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "run_browser_task",
                "args": {"task_description": f"Log into twitter and post this thread: {results[2]}"},
                "id": "call_123"
            }]
        )
        browser_res = await tool_node.ainvoke({"messages": [msg]})
        log_output = browser_res["messages"][-1].content
        results[2] += f"\n\n[Browser plan: {browser_plan}]\n[Browser execution log: {log_output}]"

    return {
        "yt_scripts": [results[0]],
        "ig_reels": [results[1]],
        "x_threads": [results[2]]
    }

async def node_branch_c_tech(state: BlackboardState) -> Dict:
    """Execute the replica/technical skill handler for software requests."""
    strategy = state.founder_strategy.get("summary", "")
    code = await skill_registry.execute_skill(
        "replica-skill",
        "Design and implement the requested technical solution. Return complete code where appropriate.",
        {"strategy": strategy, "raw_request": state.raw_thought},
    )
    return {"replica_codebase": {"implementation.md": code}, "vault_data": state.vault_data}

async def node_branch_d_coworker(state: BlackboardState) -> Dict:
    """Execute founder/master planning skills and OpenDots coworker."""
    strategy = state.founder_strategy.get("summary", "")
    context = {"strategy": strategy, "raw_request": state.raw_thought}
    skill_calls = [
        skill_registry.execute_skill("founder-skill", "Create an actionable plan for this request.", context),
        skill_registry.execute_skill("master-skills", "Coordinate relevant workstreams and list next steps.", context),
        skill_registry.execute_skill("arena-skill", "Review the proposed plan for gaps, risks and measurable success criteria.", context),
        skill_registry.execute_skill("opendots-coworker-skill", "Produce an operational coworker checklist with clear next actions.", context),
    ]
    if re.search(r"\b(invest|trading|portfolio|stock|market analysis|financial model)\b", state.raw_thought, re.I):
        skill_calls.append(skill_registry.execute_skill("trader-skill", "Analyze the financial/trading aspect and clearly state assumptions and risks.", context))
    skill_results = await asyncio.gather(*skill_calls)
    founder, master, arena_review, opendots_plan = skill_results[:4]
    coworker_task = f"Analyze the request and suggest operational next steps: {strategy}"
    tool_node = ToolNode([run_opendots_worker])
    from langchain_core.messages import AIMessage
    msg = AIMessage(content="", tool_calls=[{
        "name": "run_opendots_worker",
        "args": {"task": coworker_task, "context": {"raw_thought": state.raw_thought}},
        "id": "call_opendots_123"
    }])
    res = await tool_node.ainvoke({"messages": [msg]})
    log_output = res["messages"][-1].content
    return {"opendots_log": f"{founder}\n\n{master}\n\n{arena_review}\n\n{opendots_plan}\n\n{log_output}"}

async def node_skill_swarm(state: BlackboardState) -> Dict:
    """Run the supervisor-selected skills as parallel DAG waves over a shared blackboard."""
    artifacts = await execute_skill_plan(
        state.raw_thought,
        selected_skills=state.selected_skills,
        context={
            "mission_id": state.mission_id,
            "chat_id": state.chat_id,
            "strategy": state.founder_strategy.get("summary", ""),
        },
    )
    return {
        "skill_results": artifacts.get("skills", {}),
        "final_artifacts": artifacts,
    }


async def node_aggregator(state: BlackboardState) -> Dict:
    """Join point for the skill swarm and compatibility branches."""
    return {}

async def node_self_correction(state: BlackboardState) -> Dict:
    """Phase 4a: Self-Correction Linter Loop"""
    score = 100
    if state.yt_scripts and len(state.yt_scripts) > 0:
        try:
            score_out = await skill_registry.execute_tool('youtube-agent-skill', 'hookscore.py', [state.yt_scripts[0][:50]])
            match = re.search(r'Score for.*:\s*(\d+)', score_out)
            if match:
                score = int(match.group(1))
        except Exception:
            pass

    if score < 75 and state.retries < 2:
        yt_prompt = f"Rewrite this YouTube script to be more engaging. Previous score: {score}. Draft: {state.yt_scripts[0]}"
        new_yt = await router.generate_tier3(yt_prompt)
        return {"yt_scripts": [new_yt], "retries": state.retries + 1}

    return {"retries": state.retries}

def check_correction(state: BlackboardState):
    """Conditional Edge for self-correction routing"""
    if state.retries < 2 and "(Rewrite" in str(state.yt_scripts):
        return "self_correction"
    return "linter_humanizer"

async def node_linter_and_humanizer(state: BlackboardState) -> Dict:
    """Phase 4b: Mandatory Humanizer Gate and Final Report Compiler"""

    report_sections = []
    report_sections.append(f"### 🧠 Master Strategy\n{state.founder_strategy.get('summary', '')}\n")
    if state.selected_skills:
        report_sections.append(
            "### 🗂️ Supervisor Execution Plan\n"
            + ", ".join(state.selected_skills)
            + f"\n\nReason: {state.skill_plan_reasoning}"
        )
    if state.skill_results:
        report_sections.append("### 🤖 Specialized Skill Results")
        for skill_id in state.selected_skills:
            result = state.skill_results.get(skill_id)
            if not result:
                continue
            if result.get("status") == "failed":
                report_sections.append(f"**{skill_id} — failed**\n{result.get('error', 'Unknown error')}")
            else:
                report_sections.append(f"**{skill_id}**\n{result.get('output', '')}")

    if "branch_a_sales" in state.next_nodes and (state.b2b_emails or state.leads_csv):
        humanized_b2b = [clean_and_humanize(email) for email in state.b2b_emails if email]
        report_sections.append("### 🎯 Sales & Leads")
        report_sections.append(f"**Leads:**\n```csv\n{state.leads_csv}\n```")
        report_sections.append(f"**Outreach:**\n" + "\n\n---\n\n".join(humanized_b2b))

    if "branch_b_content" in state.next_nodes and (state.yt_scripts or state.ig_reels or state.x_threads):
        humanized_yt = [clean_and_humanize(script) for script in state.yt_scripts if script]
        humanized_ig = [clean_and_humanize(reel) for reel in state.ig_reels if reel]
        humanized_x = [clean_and_humanize(thread) for thread in state.x_threads if thread]

        report_sections.append("\n### 📱 Content Swarm")
        if humanized_yt: report_sections.append(f"**YouTube:**\n" + "\n\n".join(humanized_yt))
        if humanized_ig: report_sections.append(f"**Instagram:**\n" + "\n\n".join(humanized_ig))
        if humanized_x: report_sections.append(f"**X/Twitter:**\n" + "\n\n".join(humanized_x))

    if "branch_c_tech" in state.next_nodes and state.replica_codebase:
        report_sections.append("\n### 💻 Tech & MVP")
        for filename, code in state.replica_codebase.items():
            report_sections.append(f"**{filename}:**\n```html\n{code}\n```")

    if "branch_d_coworker" in state.next_nodes and state.opendots_log:
        report_sections.append("\n### 🤖 OpenDots Coworker Log")
        report_sections.append(state.opendots_log)

    final_report = "\n".join(report_sections)
    try:
        candidate_report = await skill_registry.execute_skill(
            "humanizer-core-skill",
            "Polish this report for clarity and natural wording without changing facts, code, IDs, or data. "
            "Preserve all section headings and all worker outputs.",
            {"report": final_report},
        )
        # A weak/mock model can return unrelated canned text. Never replace the
        # synthesized report unless the essential execution-plan structure survives.
        if candidate_report and (
            not state.selected_skills
            or "### 🗂️ Supervisor Execution Plan" in candidate_report
        ):
            final_report = candidate_report
    except Exception:
        # Preserve the compiled report if the optional humanizer model is unavailable.
        pass

    return {
        "final_report": final_report
    }


# Build LangGraph
workflow = StateGraph(BlackboardState)

workflow.add_node("supervisor", node_supervisor)
workflow.add_node("hitl_gate", node_hitl_gate)
workflow.add_node("general_chat_node", node_general_chat)
workflow.add_node("cancelled_node", node_cancelled)
workflow.add_node("skill_swarm_node", node_skill_swarm)

workflow.add_node("branch_a_sales", node_branch_a_sales)
workflow.add_node("branch_b_content", node_branch_b_content)
workflow.add_node("branch_c_tech", node_branch_c_tech)
workflow.add_node("branch_d_coworker", node_branch_d_coworker)

workflow.add_node("aggregator", node_aggregator)
workflow.add_node("self_correction", node_self_correction)
workflow.add_node("linter_humanizer", node_linter_and_humanizer)

# Define edges
workflow.set_entry_point("supervisor")
workflow.add_edge("supervisor", "hitl_gate")

workflow.add_conditional_edges(
    "hitl_gate",
    check_supervisor_routing,
    ["general_chat_node", "cancelled_node", "skill_swarm_node", "branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker", "supervisor"]
)

# Route general chat directly to end
workflow.add_edge("general_chat_node", END)
workflow.add_edge("cancelled_node", END)
workflow.add_edge("skill_swarm_node", "aggregator")

# Legacy department branches remain registered for compatibility with saved checkpoints.
# Branch in
workflow.add_edge("branch_a_sales", "aggregator")
workflow.add_edge("branch_b_content", "aggregator")
workflow.add_edge("branch_c_tech", "aggregator")
workflow.add_edge("branch_d_coworker", "aggregator")

workflow.add_edge("aggregator", "self_correction")

workflow.add_conditional_edges(
    "self_correction",
    check_correction,
    {
        "linter_humanizer": "linter_humanizer"
    }
)

workflow.add_edge("linter_humanizer", END)


async def run_orchestrator(raw_thought: str, chat_id: int, message_id: int, status_callback=None) -> Any:
    """Executes the ingestion phase of the LangGraph pipeline up to HITL pause."""
    mission_id = str(uuid.uuid4())

    initial_state = BlackboardState(
        mission_id=mission_id,
        chat_id=chat_id,
        message_id=message_id,
        raw_thought=raw_thought
    )

    config = {"configurable": {"thread_id": str(chat_id)}}

    async with AsyncSqliteSaver.from_conn_string("/tmp/langgraph_checkpoints.sqlite") as saver:
        await saver.setup()
        app_graph = workflow.compile(checkpointer=saver)

        final_state_dict = None
        # We process stream to catch any interrupt payloads
        async for event in app_graph.astream(initial_state, config=config, stream_mode="updates"):
            # event is a dict mapping node_name -> node_output
            for node_name, state_update in event.items():
                if status_callback:
                    await status_callback(f"Executing step: {node_name}...")

                # We need to manually merge the state update for the final check since we aren't using "values" stream_mode
                if not final_state_dict:
                    final_state_dict = initial_state.model_dump()
                if isinstance(state_update, dict):
                    final_state_dict.update(state_update)


        # Check if execution got interrupted
        state_snapshot = await app_graph.aget_state(config)
        if state_snapshot.next:
            # Execution is interrupted. We check tasks.
            for task in state_snapshot.tasks:
                if task.interrupts:
                    # Return the interrupt payload to caller
                    return task.interrupts[0].value

        # If it finished cleanly without interrupt (e.g. general chat)
        if final_state_dict:
            state = BlackboardState(**final_state_dict)
            if state.final_report:
                return state.final_report

    return ""


async def resume_orchestrator(chat_id: int, resume_payload: dict, status_callback=None) -> Any:
    """Resumes the graph after approval/edit."""
    config = {"configurable": {"thread_id": str(chat_id)}}

    try:
        from langgraph.types import Command
    except ImportError:
        try:
            from langgraph.graph.message import Command
        except ImportError:
            class Command:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

    input_cmd = Command(resume=resume_payload)

    async with AsyncSqliteSaver.from_conn_string("/tmp/langgraph_checkpoints.sqlite") as saver:
        await saver.setup()
        app_graph = workflow.compile(checkpointer=saver)

        final_state_dict = None

        # We need to fetch current state first to merge updates into
        current_state = await app_graph.aget_state(config)
        if current_state.values:
            final_state_dict = current_state.values.copy()

        async for event in app_graph.astream(input_cmd, config=config, stream_mode="updates"):
            for node_name, state_update in event.items():
                if status_callback:
                    await status_callback(f"Executing step: {node_name}...")

                if not final_state_dict:
                    final_state_dict = state_update if isinstance(state_update, dict) else {}
                elif isinstance(state_update, dict):
                    final_state_dict.update(state_update)


        state_snapshot = await app_graph.aget_state(config)
        if state_snapshot.next:
            for task in state_snapshot.tasks:
                if task.interrupts and task.name != "hitl_gate":
                    return task.interrupts[0].value

        if final_state_dict:
            state = BlackboardState(**final_state_dict)
            if state.final_report:
                await memory_manager.save_state(state)
                return state.final_report

    return ""
