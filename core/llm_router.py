import asyncio
import hashlib
import logging
import os
import time
from itertools import count
from typing import Optional

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from redis.asyncio import Redis
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import settings

logger = logging.getLogger(__name__)

# Prefer chat-capable NVIDIA-hosted models in a deliberate order, then append
# additional chat models discovered from the live /models endpoint.
FALLBACK_MODELS = (
    # Render logs confirmed this model succeeds; try it before flaky/deprecated candidates.
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "moonshotai/kimi-k3",
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2-thinking",
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-flash-0731",
    "deepseek-ai/deepseek-v4-pro",
    "z-ai/glm-5.3-flash",
    "z-ai/glm-5.3",
    "z-ai/glm-5.2",
    "qwen/qwen3-next-80b-a3b-instruct",
    "qwen/qwen3-next-80b-a3b-thinking",
    "qwen/qwq-32b",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-nano-30b-a3b",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "openai/gpt-oss-20b",
    "stepfun-ai/step-3.5-flash",
)
NON_CHAT_MODEL_MARKERS = (
    "embed", "rerank", "gliner", "safety", "guard", "detect", "classify",
    "image", "video", "audio", "speech", "translate", "pii",
)
MODEL_COOLDOWN_SECONDS = {402: 900, 429: 90, 500: 30, 502: 30, 503: 45, 504: 30}
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_FREE_MODEL = "openrouter/free"
CLOUDFLARE_DEFAULT_MODEL = "@cf/zai-org/glm-4.7-flash"
TRANSIENT_ERRORS = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


def _configured_value(env_name: str, settings_value: str = "") -> str:
    return (os.getenv(env_name) or settings_value or "").strip()


def _current_api_keys() -> list[str]:
    raw = os.getenv("NVIDIA_API_KEYS") or os.getenv("NVIDIA_API_KEY") or settings.NVIDIA_API_KEY
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    return keys or [""]


def _openrouter_key() -> str:
    return _configured_value("OPENROUTER_API_KEY", getattr(settings, "OPENROUTER_API_KEY", ""))


def _mock_mode() -> bool:
    keys = _current_api_keys()
    return bool(keys) and all(
        key.lower().startswith(("mock-", "test-", "mock_", "test_")) for key in keys
    )


class InMemoryTokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()

    async def consume(self, tokens: int = 1) -> bool:
        now = time.time()
        self.tokens = min(self.capacity, self.tokens + (now - self.last_refill) * self.refill_rate)
        self.last_refill = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


redis_client: Optional[Redis] = None
if settings.UPSTASH_REDIS_URL and "mock-url" not in settings.UPSTASH_REDIS_URL:
    try:
        redis_client = Redis.from_url(settings.UPSTASH_REDIS_URL)
    except Exception:
        redis_client = None

local_bucket = InMemoryTokenBucket(capacity=100, refill_rate=10.0)


async def check_rate_limit(key: str, limit: int = 100, window: int = 60) -> bool:
    if redis_client:
        try:
            current = await redis_client.get(key)
            if current and int(current) >= limit:
                return False
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window, nx=True)
            await pipe.execute()
            return True
        except Exception:
            pass
    return await local_bucket.consume(1)


class LLMRouter:
    def __init__(self):
        self._task_counter = count()
        self._task_lock = asyncio.Lock()
        self._key_index = 0
        self._model_cache: dict[str, tuple[float, list[str]]] = {}
        self._model_cooldowns: dict[tuple[str, str], float] = {}
        self._preferred_models: dict[str, str] = {}
        self._cache_seconds = 300

    async def _get_preferred_model(self, cache_key: str) -> str:
        """Return the last successful model for this provider credential."""
        preferred = self._preferred_models.get(cache_key, "")
        if preferred:
            return preferred
        if redis_client:
            try:
                value = await redis_client.get("reven:llm:preferred:" + hashlib.sha256(cache_key.encode()).hexdigest()[:24])
                if value:
                    preferred = str(value)
                    self._preferred_models[cache_key] = preferred
                    return preferred
            except Exception as exc:
                logger.debug("Preferred model Redis read skipped: %s", type(exc).__name__)
        return ""

    async def _remember_preferred_model(self, cache_key: str, model: str) -> None:
        """Remember a healthy model in memory and Redis when configured."""
        self._preferred_models[cache_key] = model
        if redis_client:
            try:
                await redis_client.set(
                    "reven:llm:preferred:" + hashlib.sha256(cache_key.encode()).hexdigest()[:24],
                    model,
                    ex=60 * 60 * 24 * 30,
                )
            except Exception as exc:
                logger.debug("Preferred model Redis write skipped: %s", type(exc).__name__)

    def _cloudflare_credentials(self) -> tuple[str, str]:
        account_id = _configured_value("CLOUDFLARE_ACCOUNT_ID", getattr(settings, "CLOUDFLARE_ACCOUNT_ID", ""))
        token = _configured_value("CLOUDFLARE_API_TOKEN", getattr(settings, "CLOUDFLARE_API_TOKEN", ""))
        return account_id, token

    async def _try_cloudflare(self, prompt: str) -> str:
        """Use Cloudflare Workers AI through its OpenAI-compatible API."""
        account_id, token = self._cloudflare_credentials()
        if not account_id or not token:
            raise RuntimeError("CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN is not configured.")
        if any(value.lower().startswith(("mock-", "test-", "mock_", "test_")) for value in (account_id, token)):
            raise RuntimeError("Cloudflare Workers AI credentials are test/mock values.")
        model = _configured_value("CLOUDFLARE_AI_MODEL", getattr(settings, "CLOUDFLARE_AI_MODEL", "")) or CLOUDFLARE_DEFAULT_MODEL
        client = AsyncOpenAI(
            api_key=token,
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
            timeout=15.0,
            max_retries=0,
        )
        return await self._call_model(client, model, prompt)

    def _base_url(self) -> str:
        gateway = _configured_value("CF_GATEWAY_URL", settings.CF_GATEWAY_URL).rstrip("/")
        if not gateway or "mock-account" in gateway:
            return "https://integrate.api.nvidia.com/v1"
        return f"{gateway}/openai/v1"

    async def _next_task_credentials(self) -> tuple[str, AsyncOpenAI]:
        async with self._task_lock:
            keys = _current_api_keys()
            key = keys[self._key_index % len(keys)]
            self._key_index = (self._key_index + 1) % max(1, len(keys))
        return key, AsyncOpenAI(api_key=key, base_url=self._base_url(), timeout=15.0, max_retries=0)

    async def _available_models(self, client: AsyncOpenAI, cache_key: str) -> list[str]:
        now = time.monotonic()
        cached = self._model_cache.get(cache_key)
        if cached and now - cached[0] < self._cache_seconds:
            return cached[1]
        try:
            response = await client.models.list()
            discovered = [
                item.id for item in response.data
                if getattr(item, "id", None)
                and not any(marker in item.id.lower() for marker in NON_CHAT_MODEL_MARKERS)
            ]
            ordered = [model for model in FALLBACK_MODELS if model in discovered]
            ordered += [model for model in discovered if model not in ordered]
            models = ordered or list(FALLBACK_MODELS)
        except Exception as exc:
            logger.warning("NVIDIA model discovery failed; using configured fallback list: %s", type(exc).__name__)
            models = list(FALLBACK_MODELS)
        self._model_cache[cache_key] = (now, models)
        return models

    async def _call_model(self, client: AsyncOpenAI, model: str, prompt: str) -> str:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    async def _try_openrouter(self, prompt: str) -> str:
        """Use OpenRouter's free-only model router when a key is configured."""
        key = _openrouter_key()
        if not key or key.lower().startswith(("mock-", "test-", "mock_", "test_")):
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")
        client = AsyncOpenAI(
            api_key=key,
            base_url=OPENROUTER_BASE_URL,
            timeout=15.0,
            max_retries=0,
            default_headers={
                "HTTP-Referer": "https://github.com/arifalish/Reven-Ashistant",
                "X-Title": "Reven Assistant",
            },
        )
        return await self._call_model(client, OPENROUTER_FREE_MODEL, prompt)

    async def _generate_nvidia(self, prompt: str) -> str:
        keys = _current_api_keys()
        _, first_client = await self._next_task_credentials()
        clients = [first_client]
        start_index = (self._key_index - 1) % len(keys)
        for index, key in enumerate(keys):
            if index != start_index:
                clients.append(AsyncOpenAI(api_key=key, base_url=self._base_url(), timeout=15.0, max_retries=0))

        last_error: Optional[Exception] = None
        attempted: set[tuple[str, str]] = set()
        for client in clients:
            key_fingerprint = hashlib.sha256((client.api_key or "").encode()).hexdigest()[:12]
            cache_key = str(client.base_url) + ":" + key_fingerprint
            models = await self._available_models(client, cache_key)
            preferred = await self._get_preferred_model(cache_key)
            if preferred and preferred in models:
                models = [preferred] + [candidate for candidate in models if candidate != preferred]
            key_auth_failed = False
            # Bound provider failover latency: do not try an unbounded catalogue for every Telegram message.
            model_attempts = 0
            for model in models:
                marker = (key_fingerprint, model)
                if marker in attempted:
                    continue
                attempted.add(marker)
                if self._model_cooldowns.get(marker, 0.0) > time.monotonic():
                    logger.debug("Skipping NVIDIA model %s during cooldown", model)
                    continue
                if model_attempts >= 4:
                    logger.warning("Reached NVIDIA per-key model attempt limit; rotating to next key")
                    break
                model_attempts += 1
                try:
                    answer = await self._call_model(client, model, prompt)
                    self._model_cooldowns.pop(marker, None)
                    await self._remember_preferred_model(cache_key, model)
                    logger.info("LLM request succeeded with NVIDIA model %s; saved as preferred", model)
                    return answer
                except APIStatusError as exc:
                    last_error = exc
                    status = exc.status
                    if status in (401, 403):
                        key_auth_failed = True
                        logger.warning("NVIDIA key rejected (HTTP %s); moving to next key", status)
                        break
                    if status in MODEL_COOLDOWN_SECONDS:
                        self._model_cooldowns[marker] = time.monotonic() + MODEL_COOLDOWN_SECONDS[status]
                        logger.info("Cooling down NVIDIA model %s after HTTP %s", model, status)
                        continue
                    if status in (400, 404, 405, 410, 422):
                        logger.debug("Skipping incompatible NVIDIA model %s (HTTP %s)", model, status)
                        continue
                    if 400 <= status < 500:
                        raise
                    continue
                except TRANSIENT_ERRORS as exc:
                    last_error = exc
                    self._model_cooldowns[marker] = time.monotonic() + 30
                    logger.info("Cooling down NVIDIA model %s after transient transport error", model)
                    continue
                except Exception as exc:
                    last_error = exc
                    logger.warning("Unexpected error from NVIDIA model %s: %s", model, type(exc).__name__)
                    continue
            if key_auth_failed:
                continue
        if last_error:
            raise RuntimeError(f"All configured NVIDIA models/keys failed; last error type: {type(last_error).__name__}") from last_error
        raise RuntimeError("No NVIDIA model is currently available (all candidates may be in cooldown).")

    async def _generate(self, prompt: str, tier: str) -> str:
        """Try free OpenRouter and Cloudflare Workers AI before NVIDIA fallback."""
        errors: list[str] = []
        if _openrouter_key():
            try:
                return await self._try_openrouter(prompt)
            except Exception as exc:
                errors.append(f"OpenRouter free router: {exc}")
        if self._cloudflare_credentials() != ("", ""):
            try:
                return await self._try_cloudflare(prompt)
            except Exception as exc:
                errors.append(f"Cloudflare Workers AI: {exc}")
        try:
            return await self._generate_nvidia(prompt)
        except Exception as exc:
            errors.append(f"NVIDIA fallback: {exc}")
        if _mock_mode():
            return self._mock_response(prompt, tier)
        raise RuntimeError("All configured AI providers failed. " + " | ".join(errors))

    @staticmethod
    def _mock_response(prompt: str, tier: str) -> str:
        if tier == "tier1":
            if "Analyze the following user task/thought" in prompt:
                return '["branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker"]'
            return (
                "# Strategy & Unit Economics\n\nMock strategy for tests only.\n\n"
                "## Plan\n1. Validate the request.\n2. Execute configured skills.\n"
                "3. Report verified outcomes."
            )
        if tier == "tier2":
            return "<!DOCTYPE html><html lang='en'><body><h1>Mock response for tests only</h1></body></html>"
        if "YouTube" in prompt:
            return "# Test Hook\n\nMock YouTube draft for automated tests."
        if "Instagram" in prompt or "Reel" in prompt:
            return "Mock Instagram draft for automated tests."
        if "B2B" in prompt or "emails" in prompt:
            return "Subject: Test only\n\nMock outreach draft for automated tests."
        return "Mock content draft for automated tests."

    async def _tier(self, prompt: str, tier: str, limit: int) -> str:
        while not await check_rate_limit(f"{tier}_rl", limit=limit, window=60):
            await asyncio.sleep(1)
        return await self._generate(prompt, tier)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(TRANSIENT_ERRORS))
    async def generate_tier1(self, prompt: str) -> str:
        return await self._tier(prompt, "tier1", 50)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(TRANSIENT_ERRORS))
    async def generate_tier2(self, prompt: str) -> str:
        return await self._tier(prompt, "tier2", 50)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(TRANSIENT_ERRORS))
    async def generate_tier3(self, prompt: str) -> str:
        return await self._tier(prompt, "tier3", 100)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5),
           retry=retry_if_exception_type(TRANSIENT_ERRORS))
    async def generate_tier4(self, prompt: str) -> str:
        try:
            return await self._tier(prompt, "tier4", 200)
        except Exception as primary_error:
            groq_key = _configured_value("GROQ_API_KEY", settings.GROQ_API_KEY)
            if not groq_key or groq_key.lower().startswith(("mock-", "test-", "mock_", "test_")):
                if _mock_mode():
                    return f"[Mocked Tier 4 Response for tests] {prompt[:50]}..."
                raise primary_error
            client = AsyncOpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1", timeout=15.0, max_retries=0)
            try:
                return await self._call_model(client, "llama-3.3-70b-versatile", prompt)
            except Exception:
                raise primary_error


router = LLMRouter()
