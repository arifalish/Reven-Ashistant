import re

with open('core/orchestrator_graph.py', 'r') as f:
    content = f.read()

# Modify run_orchestrator signature and logic
new_run = """async def run_orchestrator(raw_thought: str, chat_id: int, message_id: int, status_callback=None) -> Any:
    \"\"\"Executes the ingestion phase of the LangGraph pipeline up to HITL pause.\"\"\"
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
"""
content = re.sub(r'async def run_orchestrator.*?return ""', new_run, content, flags=re.DOTALL)


new_resume = """async def resume_orchestrator(chat_id: int, resume_payload: dict, status_callback=None) -> Any:
    \"\"\"Resumes the graph after approval/edit.\"\"\"
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
                    final_state_dict = state_update
                else:
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
"""
content = re.sub(r'async def resume_orchestrator.*(?=\n\n$|\Z)', new_resume, content, flags=re.DOTALL)

with open('core/orchestrator_graph.py', 'w') as f:
    f.write(content)
