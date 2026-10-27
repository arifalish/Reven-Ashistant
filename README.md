# README updated for the 15-skill architecture

# Reven-Ashistant

This repository contains a centralized supervisor + skill-swarm architecture for autonomous agent execution.

## Runtime architecture
- Central orchestrator in `core/orchestrator_graph.py`
- Shared memory in `core/blackboard_memory.py`
- Skill registry in `core/skill_loader.py`
- Supervisor routing in `core/supervisor_router.py`

## Active skill catalog
- instagram-agent-skill
- youtube-agent-skill
- linkedin-agent-skill
- x-agent-skill
- founder-skill
- trader-skill
- replica-skill
- arena-skill
- master-skills
- google-maps-scraper-kit
- sales-desk-skill
- humanizer-core-skill
- seo-agent-skill
- browser-automation-skill
- opendots-skill

## Render deployment
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The app includes a `/health` endpoint for deployment health checks.
