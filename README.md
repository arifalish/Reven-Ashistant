# Reven-Ashistant

Natural-language multi-agent assistant built with FastAPI, LangGraph and a centralized skill supervisor.

## Deploy on Render

1. Create a Render Blueprint from this repository. Render reads `render.yaml` and builds the Dockerfile.
2. Set `NVIDIA_API_KEY` to a valid NVIDIA NIM API key and `TELEGRAM_BOT_TOKEN` to the token from BotFather. Do not leave either as a mock/default value. The LLM router now discovers available NVIDIA models at runtime and fails over when a model is retired or unsupported. It re-reads environment credentials on each task. For key rotation, optionally set `NVIDIA_API_KEYS` to a comma-separated list of valid NVIDIA keys; protect these as Render secrets. API keys are static credentials, not refreshable OAuth tokens, so create/rotate them in NVIDIA's console and update Render when needed.
3. Deploy. At container startup, `scripts/start.py` uses Render's `RENDER_EXTERNAL_URL` to call Telegram `setWebhook` automatically and supplies `TELEGRAM_WEBHOOK_SECRET` when configured. You do not need to set the webhook manually if Telegram accepts the request.
4. Open the Render service URL and check `GET /` for the health response. Check Render logs for the line `Telegram webhook configured`. If auto-configuration fails, logs show a warning and the service still starts; configure the webhook manually to `https://YOUR-RENDER-SERVICE.onrender.com/api/v1/orchestrate`.
5. Optional integrations:
   - `OPENAI_API_KEY`: browser-use research, where the browser agent is enabled.
   - `GOOGLE_MAPS_SCRAPER_URL`: separately deployed compatible Maps-scraper endpoint.
   - `UPSTASH_REDIS_URL`: Redis for shared mission memory/rate limiting where supported.
   - `FIREBASE_CREDS`: path to a Firebase service-account JSON file mounted inside the container. Never commit credentials.

## Architecture

- **Ingestion:** FastAPI validates Telegram webhook secrets and enqueues updates for background processing.
- **Supervisor:** `core/skill_supervisor.py` validates plans against a registry of 15 skill IDs and has deterministic routing fallback.
- **DAG execution:** independent skills run concurrently; declared dependencies run in later waves, with outputs recorded in the shared skill blackboard.
- **Approval gate:** work tasks pause for explicit Telegram approval before execution.
- **Memory:** LangGraph checkpoints are stored in `/tmp`; Redis/Firestore persistence is optional.
- **Skill definitions:** the Docker build bootstraps specialized `SKILL.md` instructions for all 15 skills.

## Operational boundaries

- The task queue is process-local. Jobs can be lost on restart and are not shared between Render instances. Use a durable Redis-backed queue before scaling to multiple instances.
- LLM-backed skills can produce plans, copy, code and analysis. Browser automation, live Maps scraping, social posting and persistent OpenDots shell work need their respective real integrations and credentials.
- The default bootstrap creates skill instruction packages; it does not clone third-party skill repositories.
- Never commit API keys, Telegram tokens, Firebase service-account JSON, cookies or other credentials.

## Local checks

```bash
pip install -r requirements.txt
bash scripts/bootstrap_skills.sh
pytest -q
```
