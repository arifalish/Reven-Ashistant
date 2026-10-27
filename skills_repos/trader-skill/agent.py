import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'trader-skill',
    'task': task,
    'context': context,
    'output': f"Trader research agent summarized market opportunities and risk context for: {task or 'the request'}"
}

print(json.dumps(response))
