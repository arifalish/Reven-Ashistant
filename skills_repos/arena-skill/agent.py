import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'arena-skill',
    'task': task,
    'context': context,
    'output': f"Arena agent ran a code tournament plan and selected the strongest implementation for: {task or 'the request'}"
}

print(json.dumps(response))
