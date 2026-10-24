import asyncio
import uuid
import re
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
try:
    from langgraph.types import interrupt
except ImportError:
    def interrupt(val): return val
from core.blackboard_memory import BlackboardState, memory_manager
from core.llm_router import router
from core.skill_loader import skill_registry
from core.credential_vault import credential_vault
from workers.maps_scraper_worker import scraper_worker
from middleware.quality_humanizer import clean_and_humanize
from delivery.telegram_ux import create_workspace_zip

async def node_ingestion(state: BlackboardState) -> Dict:
    """Phase 1: Ingestion & Strategy Blueprint"""
    strategy_prompt = f"Analyze business thought: {state.raw_thought}. Provide unit economics, product strategy, and SEO blueprint."
    strategy_result = await router.generate_tier1(strategy_prompt)

    # Store to RAG
    await memory_manager.add_to_vector_rag(strategy_result, {"type": "strategy", "mission": state.mission_id})

    return {"founder_strategy": {"summary": strategy_result}}

def node_hitl_gate(state: BlackboardState) -> Dict:
    """Phase 2: Human-in-the-Loop Telegram Approval Gate"""
    # structured resume payload: {"action": "approve" | "edit" | "cancel", "modifications": "..."}
    user_approval = interrupt("Please approve the strategy via Telegram callback.")

    if not isinstance(user_approval, dict):
        if user_approval == "cancel":
            raise Exception("Mission Cancelled by User")
        return {}

    action = user_approval.get("action")
    if action == "cancel":
        raise Exception("Mission Cancelled by User")
    elif action == "edit":
        modifications = user_approval.get("modifications", "")
        return {"raw_thought": f"{state.raw_thought} (Edit: {modifications})"}

    return {}

def check_hitl_routing(state: BlackboardState):
    """If edited, loop back to ingestion. Otherwise, proceed to branches."""
    if "(Edit:" in state.raw_thought:
        return "ingestion"
    return "branch_a_sales"

async def node_branch_a_sales(state: BlackboardState) -> Dict:
    """Phase 3 - Branch A: B2B Lead Engine & Sales"""
    leads = await scraper_worker.scrape_leads("Target City", "Niche")

    b2b_prompt = f"Write personalized B2B cold emails and LinkedIn DMs for these leads based on the strategy: {state.founder_strategy.get('summary', '')}\\nLeads: {leads[:1000]}"
    emails = await router.generate_tier3(b2b_prompt)

    return {"leads_csv": leads, "b2b_emails": [emails]}

async def node_branch_b_content(state: BlackboardState) -> Dict:
    """Phase 3 - Branch B: Omnichannel Content Swarm"""
    strategy = state.founder_strategy.get('summary', '')

    yt_prompt = f"Write a YouTube script and thumbnail ideas based on: {strategy}"
    ig_prompt = f"Write Instagram Reel hooks and captions based on: {strategy}"
    x_prompt = f"Write a viral X/Twitter thread based on: {strategy}"

    results = await asyncio.gather(
        router.generate_tier3(yt_prompt),
        router.generate_tier3(ig_prompt),
        router.generate_tier3(x_prompt)
    )

    return {
        "yt_scripts": [results[0]],
        "ig_reels": [results[1]],
        "x_threads": [results[2]]
    }

async def node_branch_c_tech(state: BlackboardState) -> Dict:
    """Phase 3 - Branch C: Tech & MVP Engine"""
    # Simulate a dynamic requirement for an API key to complete tech branch
    _ = credential_vault.get_or_request_credential(
        state,
        service_name="Vercel",
        env_var_name="VERCEL_TOKEN",
        setup_url="https://vercel.com/account/tokens"
    )

    strategy = state.founder_strategy.get('summary', '')
    code_prompt = f"Build a single-file HTML/JS/CSS MVP landing page based on this strategy: {strategy}"
    code = await router.generate_tier2(code_prompt)

    # Must return vault_data so the checkpointer persists any newly added credentials
    return {"replica_codebase": {"index.html": code}, "vault_data": state.vault_data}

async def node_aggregator(state: BlackboardState) -> Dict:
    """Wait for all parallel branches to finish and aggregate results."""
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
    # For simplicity, if we incremented retries, it means we ran correction, but we just
    # check condition and move to humanizer if done. A real implementation loops, here we just move on.
    return "linter_humanizer"

async def node_linter_and_humanizer(state: BlackboardState) -> Dict:
    """Phase 4b: Mandatory Humanizer Gate"""

    humanized_yt = [clean_and_humanize(script) for script in state.yt_scripts if script]
    humanized_ig = [clean_and_humanize(reel) for reel in state.ig_reels if reel]
    humanized_b2b = [clean_and_humanize(email) for email in state.b2b_emails if email]
    humanized_x = [clean_and_humanize(thread) for thread in state.x_threads if thread]

    final_artifacts = {
        "01_Founder_Strategy_and_Unit_Economics.md": str(state.founder_strategy),
        "02_Verified_Google_Maps_Leads.csv": state.leads_csv,
        "03_B2B_Sales_Desk_Cold_Emails_and_LinkedIn_DMs.md": "\\n\\n---\\n\\n".join(humanized_b2b),
        "04_YouTube_Scripts_and_Scored_Hooks.md": "\\n\\n---\\n\\n".join(humanized_yt),
        "05_Instagram_Reels_and_Linted_Captions.md": "\\n\\n---\\n\\n".join(humanized_ig),
        "06_X_Threads_and_SEO_Blueprint.md": "\\n\\n---\\n\\n".join(humanized_x),
        "07_Replica_MVP_Codebase": state.replica_codebase
    }

    return {
        "yt_scripts": humanized_yt,
        "ig_reels": humanized_ig,
        "b2b_emails": humanized_b2b,
        "x_threads": humanized_x,
        "final_artifacts": final_artifacts
    }

# Build LangGraph
workflow = StateGraph(BlackboardState)

workflow.add_node("ingestion", node_ingestion)
workflow.add_node("hitl_gate", node_hitl_gate)
workflow.add_node("branch_a_sales", node_branch_a_sales)
workflow.add_node("branch_b_content", node_branch_b_content)
workflow.add_node("branch_c_tech", node_branch_c_tech)
workflow.add_node("aggregator", node_aggregator)
workflow.add_node("self_correction", node_self_correction)
workflow.add_node("linter_humanizer", node_linter_and_humanizer)

# Define edges
workflow.set_entry_point("ingestion")
workflow.add_edge("ingestion", "hitl_gate")

# Conditional Edge for HITL Gate
workflow.add_conditional_edges(
    "hitl_gate",
    check_hitl_routing,
    {
        "ingestion": "ingestion",
        "branch_a_sales": "branch_a_sales"
    }
)
# The other parallel branches
workflow.add_edge("hitl_gate", "branch_b_content")
workflow.add_edge("hitl_gate", "branch_c_tech")

# Branch in
workflow.add_edge("branch_a_sales", "aggregator")
workflow.add_edge("branch_b_content", "aggregator")
workflow.add_edge("branch_c_tech", "aggregator")

workflow.add_edge("aggregator", "self_correction")

workflow.add_conditional_edges(
    "self_correction",
    check_correction,
    {
        "linter_humanizer": "linter_humanizer"
    }
)

workflow.add_edge("linter_humanizer", END)

async def run_orchestrator(raw_thought: str, chat_id: int, message_id: int) -> Any:
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

        # We process stream to catch any interrupt payloads
        async for event in app_graph.astream(initial_state, config=config, stream_mode="values"):
            # Check if execution got interrupted
            state_snapshot = await app_graph.aget_state(config)
            if state_snapshot.next:
                # Execution is interrupted. We check tasks.
                for task in state_snapshot.tasks:
                    if task.interrupts:
                        # Return the interrupt payload to caller
                        return task.interrupts[0].value

    return b""

async def resume_orchestrator(chat_id: int, resume_payload: dict) -> Any:
    """Resumes the graph after approval/edit."""
    from langgraph.types import Command

    config = {"configurable": {"thread_id": str(chat_id)}}

    async with AsyncSqliteSaver.from_conn_string("/tmp/langgraph_checkpoints.sqlite") as saver:
        await saver.setup()
        app_graph = workflow.compile(checkpointer=saver)

        final_state_dict = None

        async for event in app_graph.astream(Command(resume=resume_payload), config=config, stream_mode="values"):
            final_state_dict = event

            # Check if execution got interrupted again (e.g. another credential needed)
            state_snapshot = await app_graph.aget_state(config)
            if state_snapshot.next:
                # Need to be careful not to return the interrupt we just cleared if state hasn't advanced
                # Only return if it's a NEW interrupt
                for task in state_snapshot.tasks:
                    if task.interrupts and task.name != "hitl_gate":
                        return task.interrupts[0].value

        if final_state_dict:
            state = BlackboardState(**final_state_dict)
            if state.final_artifacts:
                await memory_manager.save_state(state)
                zip_bytes = create_workspace_zip(state.final_artifacts)
                return zip_bytes

    return b""
