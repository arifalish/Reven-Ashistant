import re

with open('core/orchestrator_graph.py', 'r') as f:
    content = f.read()

# Fix final_state_dict.update logic
# Since stream_mode="updates" yields `event` as {node_name: {updated_state_fields}}
new_run = """
                # We need to manually merge the state update for the final check since we aren't using "values" stream_mode
                if not final_state_dict:
                    final_state_dict = initial_state.model_dump()
                if isinstance(state_update, dict):
                    final_state_dict.update(state_update)
"""

content = content.replace("""
                # We need to manually merge the state update for the final check since we aren't using "values" stream_mode
                if not final_state_dict:
                    final_state_dict = initial_state.model_dump()
                final_state_dict.update(state_update)""", new_run)

new_resume = """
                if not final_state_dict:
                    final_state_dict = state_update if isinstance(state_update, dict) else {}
                elif isinstance(state_update, dict):
                    final_state_dict.update(state_update)
"""

content = content.replace("""
                if not final_state_dict:
                    final_state_dict = state_update
                else:
                    final_state_dict.update(state_update)""", new_resume)


with open('core/orchestrator_graph.py', 'w') as f:
    f.write(content)
