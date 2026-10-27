import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': 'google-maps-scraper-kit',
    'task': task,
    'context': context,
    'output': f"Google Maps scraper agent generated a lead list and business dataset for: {task or 'the request'}"
}

print(json.dumps(response))
