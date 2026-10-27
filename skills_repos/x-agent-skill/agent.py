import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'x-agent-skill',
    'task': task,
    'context': context,
    'output': f"X/Twitter agent drafted a viral thread and hook sequence for: {task or 'the request'}"
}

print(json.dumps(response))
