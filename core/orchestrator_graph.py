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

async def node_supervisor(state: BlackboardState) -> Dict:
    """Phase 1: Dynamic Supervisor & Routing"""

    # 1. Decide routing
    next_nodes = await analyze_task_and_route(state.raw_thought)

    # 2. If it's just a general chat, generate response immediately
    general_response = ""
    if "general_chat" in next_nodes:
        prompt = f"Answer the following query clearly and concisely:\n{state.raw_thought}"
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
    """Phase 2: Human-in-the-Loop Gateway"""
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
    """Route to appropriate nodes based on supervisor decision."""
    if "general_chat" in state.next_nodes:
        return ["general_chat_node"]

    if "(Edit:" in state.raw_thought:
        return ["supervisor"]

    # Launch approved branches in parallel
    valid_branches = [n for n in state.next_nodes if n != "general_chat"]
    return valid_branches

async def node_general_chat(state: BlackboardState) -> Dict:
    """Handles general conversational queries."""
    return {"final_report": state.general_response}
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

    # Dynamic LLM routing to the browser tool if requested by the user
    # Binds the LangChain tool and parses it into a ToolNode equivalent output
    if "post to twitter" in state.raw_thought.lower():
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
        results[2] += f"\n\n[Browser execution log: {log_output}]"

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

async def node_branch_d_coworker(state: BlackboardState) -> Dict:
    """Phase 3 - Branch D: OpenDots Coworker"""

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
    if state.retries < 2 and "(Rewrite" in str(state.yt_scripts):
        return "self_correction"
    return "linter_humanizer"

async def node_linter_and_humanizer(state: BlackboardState) -> Dict:
    """Phase 4b: Mandatory Humanizer Gate and Final Report Compiler"""

    report_sections = []
    report_sections.append(f"### 🧠 Master Strategy\n{state.founder_strategy.get('summary', '')}\n")

    if "branch_a_sales" in state.next_nodes:
        humanized_b2b = [clean_and_humanize(email) for email in state.b2b_emails if email]
        report_sections.append("### 🎯 Sales & Leads")
        report_sections.append(f"**Leads:**\n```csv\n{state.leads_csv}\n```")
        report_sections.append(f"**Outreach:**\n" + "\n\n---\n\n".join(humanized_b2b))

    if "branch_b_content" in state.next_nodes:
        humanized_yt = [clean_and_humanize(script) for script in state.yt_scripts if script]
        humanized_ig = [clean_and_humanize(reel) for reel in state.ig_reels if reel]
        humanized_x = [clean_and_humanize(thread) for thread in state.x_threads if thread]

        report_sections.append("\n### 📱 Content Swarm")
        if humanized_yt: report_sections.append(f"**YouTube:**\n" + "\n\n".join(humanized_yt))
        if humanized_ig: report_sections.append(f"**Instagram:**\n" + "\n\n".join(humanized_ig))
        if humanized_x: report_sections.append(f"**X/Twitter:**\n" + "\n\n".join(humanized_x))

    if "branch_c_tech" in state.next_nodes:
        report_sections.append("\n### 💻 Tech & MVP")
        for filename, code in state.replica_codebase.items():
            report_sections.append(f"**{filename}:**\n```html\n{code}\n```")

    if "branch_d_coworker" in state.next_nodes:
        report_sections.append("\n### 🤖 OpenDots Coworker Log")
        report_sections.append(state.opendots_log)

    final_report = "\n".join(report_sections)

    return {
        "final_report": final_report
    }


# Build LangGraph
workflow = StateGraph(BlackboardState)

workflow.add_node("supervisor", node_supervisor)
workflow.add_node("hitl_gate", node_hitl_gate)
workflow.add_node("general_chat_node", node_general_chat)

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
    ["general_chat_node", "branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker", "supervisor"]
)

# Route general chat directly to end
workflow.add_edge("general_chat_node", END)

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

        final_state_dict = None
        # We process stream to catch any interrupt payloads
        async for event in app_graph.astream(initial_state, config=config, stream_mode="values"):
            final_state_dict = event

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

async def resume_orchestrator(chat_id: int, resume_payload: dict) -> Any:
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
        async for event in app_graph.astream(input_cmd, config=config, stream_mode="values"):
            final_state_dict = event

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
