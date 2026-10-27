import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'master-skills',
    'task': task,
    'context': context,
    'output': f"Master skill agent synthesized the combined execution plan for: {task or 'the request'}"
}

print(json.dumps(response))
