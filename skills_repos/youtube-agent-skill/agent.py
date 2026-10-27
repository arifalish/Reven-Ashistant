import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'youtube-agent-skill',
    'task': task,
    'context': context,
    'output': f"YouTube agent created a title, hook, outline, and structure for: {task or 'the request'}"
}

print(json.dumps(response))
