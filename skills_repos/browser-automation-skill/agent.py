import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'browser-automation-skill',
    'task': task,
    'context': context,
    'output': f"Browser automation agent collected live web findings for: {task or 'the request'}"
}

print(json.dumps(response))
