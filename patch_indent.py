import re

with open('core/orchestrator_graph.py', 'r') as f:
    content = f.read()

# find def resume_orchestrator
start_idx = content.find("async def resume_orchestrator")

if start_idx != -1:
    old_code = content[start_idx:]

    # We notice line 257 to 260 creates a saver but then leaves it hanging
    # Then tries to do try/except
    # Then line 273 creates ANOTHER saver context block.
    # We should merge them correctly.

    new_code = """async def resume_orchestrator(chat_id: int, resume_payload: dict) -> Any:
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
        async for event in app_graph.astream(input_cmd, config=config, stream_mode="values"):
            final_state_dict = event

        state_snapshot = await app_graph.aget_state(config)
        if state_snapshot.next:
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
"""

    content = content[:start_idx] + new_code

    with open('core/orchestrator_graph.py', 'w') as f:
        f.write(content)
        print("Patched.")
