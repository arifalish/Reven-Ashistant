with open('core/orchestrator_graph.py', 'r') as f:
    content = f.read()

content = content.replace(
    'prompt = f"Answer the following query clearly and concisely:\n{state.raw_thought}"',
    'prompt = f"Answer the following query clearly and concisely:\\n{state.raw_thought}"'
)

with open('core/orchestrator_graph.py', 'w') as f:
    f.write(content)
