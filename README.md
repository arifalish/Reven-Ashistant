# Reven-Ashistant

Natural-language multi-agent assistant built with FastAPI, LangGraph and a centralized skill supervisor.

## Deploy on Render

1. Push this repository to GitHub and create a new Render Blueprint from the repository. Render will read `render.yaml` and build the included `Dockerfile`.
2. Set `NVIDIA_API_KEY` to a valid NVIDIA NIM API key. The LLM router uses the NVIDIA OpenAI-compatible endpoint when `CF_GATEWAY_URL` is left at the supplied mock-account URL.
3. Set `TELEGRAM_BOT_TOKEN` to the bot token from BotFather.
4. Configure your Telegram webhook to POST Telegram updates to `https://YOUR-RENDER-SERVICE.onrender.com/api/v1/orchestrate`. Protect that endpoint with a webhook secret at the edge/proxy if it is exposed publicly.
5. Optional persistent services:
   - `UPSTASH_REDIS_URL`: Redis connection URL for mission memory/rate limiting.
   - `FIREBASE_CREDS`: path to a Firebase service-account JSON file available inside the container. Prefer a mounted secret file; do not commit credentials.
   - `GOOGLE_MAPS_SCRAPER_URL`: URL for a separately deployed compatible Maps-scraper service.
6. Check `GET /` for the service health response.

## Architecture

- **Ingestion:** FastAPI accepts Telegram updates and enqueues them for background processing.
- **Supervisor:** `core/skill_supervisor.py` validates the LLM plan against a registry of 15 skill IDs and uses deterministic routing when the model is unavailable.
- **DAG execution:** independent skills run concurrently in a wave; declared dependencies run in later waves. Each result is written to the shared skill-artifact blackboard.
- **Approval gate:** the LangGraph flow pauses for approval before work branches execute.
- **Memory:** LangGraph checkpoints are written to SQLite under `/tmp`; mission memory can use Redis/Firestore when configured.
- **Skill definitions:** the Docker build bootstraps specialized `SKILL.md` instructions for all 15 skills.

## Current operational boundaries

- The async queue is process-local; queued tasks can be lost when the service restarts and are not shared across multiple Render instances. For production multi-instance reliability, replace it with a Redis-backed queue and idempotent job state.
- LLM-backed skills produce plans, copy, code and analysis. Browser automation, live website research, Google Maps scraping, posting to social networks and long-running OpenDots shell work require the corresponding service/tool and credentials to be configured. The system must label unavailable integrations rather than inventing results.
- The default skill bootstrap creates instruction packages; it does not clone external skill repositories.
- Never commit API keys, Telegram tokens, Firebase service-account JSON, cookies or other credentials.

## Local checks

```bash
pip install -r requirements.txt
bash scripts/bootstrap_skills.sh
pytest -q
```
