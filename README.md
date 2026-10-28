# Reven-Ashistant

Natural-language multi-agent assistant built with FastAPI, LangGraph and a centralized skill supervisor.

## Deploy on Render

1. Create a Render Blueprint from this repository. Render reads `render.yaml` and builds the Dockerfile.
2. Set `TELEGRAM_BOT_TOKEN` to the token from BotFather. For AI providers, add whichever credentials you have: `OPENROUTER_API_KEY` (free-only OpenRouter router), `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` (Workers AI), and/or `NVIDIA_API_KEY` / `NVIDIA_API_KEYS` (NVIDIA NIM). The router tries configured OpenRouter first, then Cloudflare Workers AI, then NVIDIA models. NVIDIA failover prefers Kimi K3/K2, DeepSeek, GLM, Qwen, Nemotron, Llama and other discovered chat models. It queries NVIDIA's live model list, skips non-chat model families, tries the next model after model-specific rate/quota/server failures, and places failing model/key pairs in an in-memory cooldown (429: 90 seconds; 402: 15 minutes; transient 5xx: 30–45 seconds). It also tries configured NVIDIA API keys in rotation. Cooldowns reset on service restart; use Redis-backed shared state if multi-instance or restart-persistent cooldowns are required. This improves resilience but cannot bypass account-wide quotas or provider outages. Cloudflare defaults to `@cf/zai-org/glm-4.7-flash`; override with `CLOUDFLARE_AI_MODEL` if needed. On Cloudflare Free, usage is limited to 10,000 Neurons/day; once exhausted, Cloudflare requests fail and the router tries the next configured provider. Keep all keys in Render Environment secrets, never commit them.
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
