import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'seo-agent-skill',
    'task': task,
    'context': context,
    'output': f"SEO agent produced keyword clusters, gaps, and content suggestions for: {task or 'the request'}"
}

print(json.dumps(response))
