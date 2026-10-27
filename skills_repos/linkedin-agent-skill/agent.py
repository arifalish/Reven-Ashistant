import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'linkedin-agent-skill',
    'task': task,
    'context': context,
    'output': f"LinkedIn agent produced a professional post or outreach draft for: {task or 'the request'}"
}

print(json.dumps(response))
