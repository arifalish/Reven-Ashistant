#!/bin/bash

SKILLS_DIR="skills_repos"
mkdir -p "$SKILLS_DIR"
cd "$SKILLS_DIR" || exit 1

SKILLS=(
  "instagram-agent-skill"
  "youtube-agent-skill"
  "linkedin-agent-skill"
  "x-agent-skill"
  "founder-skill"
  "trader-skill"
  "replica-skill"
  "arena-skill"
  "master-skills"
  "google-maps-scraper-kit"
  "sales-desk-skill"
  "humanizer-core-skill"
  "seo-agent-skill"
  "browser-automation-skill"
  "opendots-skill"
)

for skill in "${SKILLS[@]}"; do
  if [ ! -d "$skill" ]; then
    mkdir -p "$skill/templates"
    mkdir -p "$skill/skills"

    cat > "$skill/README.md" <<EOF
# $skill

This directory contains the runtime wrapper for the $skill agent.
EOF

    cat > "$skill/templates/voice.md" <<EOF
Voice template for $skill
EOF

    cat > "$skill/agent.py" <<PY
import json
import sys

payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
task = payload.get('task', '')
context = payload.get('context', {})

response = {
    'status': 'completed',
    'skill': '$skill',
    'task': task,
    'context': context,
    'output': f"{task or 'Task'} handled by $skill with a generated runtime response."
}

print(json.dumps(response))
PY

    echo "Created $skill"
  else
    echo "$skill already exists. Skipping."
  fi
done

echo "Bootstrap complete."
