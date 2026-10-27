import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'opendots-skill',
    'task': task,
    'context': context,
    'output': f"OpenDots worker executed the autonomous follow-up task plan for: {task or 'the request'}"
}

print(json.dumps(response))
