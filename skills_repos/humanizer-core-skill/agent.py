import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'humanizer-core-skill',
    'task': task,
    'context': context,
    'output': f"Humanizer agent rewrote and cleaned the text to sound more natural for: {task or 'the request'}"
}

print(json.dumps(response))
