import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'founder-skill',
    'task': task,
    'context': context,
    'output': f"Founder strategy agent framed a GTM, offer, and unit-economics plan for: {task or 'the request'}"
}

print(json.dumps(response))
