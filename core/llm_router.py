import asyncio
import hashlib
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


# Prefer the current catalog, but discover models from the account's /v1/models
# endpoint at runtime. The static list is only a fallback if discovery is unavailable.
FALLBACK_MODELS = (
    "nvidia/deepseek-v4.1-flash",
    "deepseek-ai/deepseek-v4-flash-0731",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "qwen/qwen3-next-80b-a3b-instruct",
    "meta/llama-3.1-8b-instruct",
)
TRANSIENT_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)


def _current_api_keys() -> list[str]:
    """Re-read environment on every task so Render secret rotations take effect."""
    raw = os.getenv("NVIDIA_API_KEYS") or os.getenv("NVIDIA_API_KEY") or settings.NVIDIA_API_KEY
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    return keys or [""]


def _mock_mode() -> bool:
    return all(
        key.lower().startswith(("mock-", "test-", "mock_", "test_"))
        for key in _current_api_keys()
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
    """Check a Redis fixed-window limit, falling back to an in-process token bucket."""
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
        self._cache_seconds = 300

        # Groq credentials are also read afresh for each call.
        self.groq_client = AsyncOpenAI(
            api_key=os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

    def _base_url(self) -> str:
        gateway = (os.getenv("CF_GATEWAY_URL") or settings.CF_GATEWAY_URL or "").rstrip("/")
        if not gateway or "mock-account" in gateway:
            return "https://integrate.api.nvidia.com/v1"
        return f"{gateway}/openai/v1"

    async def _next_task_credentials(self) -> tuple[str, AsyncOpenAI]:
        # A new task starts with the next configured key. Keys may be supplied as a
        # comma-separated NVIDIA_API_KEYS secret; a single NVIDIA_API_KEY also works.
        async with self._task_lock:
            keys = _current_api_keys()
            key = keys[self._key_index % len(keys)]
            self._key_index = (self._key_index + 1) % max(1, len(keys))
        client = AsyncOpenAI(api_key=key, base_url=self._base_url(), timeout=45.0, max_retries=0)
        return key, client

    async def _available_models(self, client: AsyncOpenAI, cache_key: str) -> list[str]:
        now = time.monotonic()
        cached = self._model_cache.get(cache_key)
        if cached and now - cached[0] < self._cache_seconds:
            return cached[1]
        try:
            response = await client.models.list()
            discovered = [item.id for item in response.data if getattr(item, "id", None)]
            # Keep catalog order as provider returned it, but try preferred agent-capable
            # models first when present.
            ordered = [model for model in FALLBACK_MODELS if model in discovered]
            ordered += [model for model in discovered if model not in ordered]
            models = ordered or list(FALLBACK_MODELS)
        except Exception:
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

    async def _generate(self, prompt: str, tier: str) -> str:
        """Discover models and fail over on retired/unsupported model IDs."""
        keys = _current_api_keys()
        # Rotate start key per task and retry other configured keys only on auth errors.
        _, first_client = await self._next_task_credentials()
        clients = [first_client]
        for key in keys:
            if key != keys[(self._key_index - 1) % len(keys)]:
                clients.append(AsyncOpenAI(api_key=key, base_url=self._base_url(), timeout=45.0, max_retries=0))

        last_error: Optional[Exception] = None
        attempted: set[tuple[str, str]] = set()
        for client in clients:
            try:
                cache_key = client.base_url + ":" + hashlib.sha256((client.api_key or "").encode()).hexdigest()[:12]\n                models = await self._available_models(client, cache_key)
            except Exception:
                models = list(FALLBACK_MODELS)
            for model in models:
                marker = (client.api_key, model)
                if marker in attempted:
                    continue
                attempted.add(marker)
                try:
                    return await self._call_model(client, model, prompt)
                except APIStatusError as exc:
                    last_error = exc
                    # Permanent model/account errors should trigger model/key failover,
                    # not exponential retries of the same retired model.
                    if exc.status in (400, 401, 403, 404, 410):
                        if exc.status in (401, 403):
                            break
                        continue
                    if exc.status == 429 or exc.status >= 500:
                        continue
                    raise
                except TRANSIENT_ERRORS as exc:
                    last_error = exc
                    continue

        if _mock_mode():
            return self._mock_response(prompt, tier)
        if last_error:
            raise RuntimeError(
                "All configured NVIDIA models/keys failed. Check NVIDIA_API_KEY or "
                "NVIDIA_API_KEYS in Render and confirm at least one model is enabled for this key. "
                f"Last provider error: {last_error}"
            ) from last_error
        raise RuntimeError("No usable NVIDIA model or API key was available.")

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
        """Master coordination, founder strategy and supervisor routing."""
        return await self._tier(prompt, "tier1", 50)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(TRANSIENT_ERRORS))
    async def generate_tier2(self, prompt: str) -> str:
        """Code and reverse-engineering tier."""
        return await self._tier(prompt, "tier2", 50)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(TRANSIENT_ERRORS))
    async def generate_tier3(self, prompt: str) -> str:
        """Creative and content generation tier."""
        return await self._tier(prompt, "tier3", 100)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5),
           retry=retry_if_exception_type(TRANSIENT_ERRORS))
    async def generate_tier4(self, prompt: str) -> str:
        """Bulk generation tier with Groq fallback."""
        try:
            return await self._tier(prompt, "tier4", 200)
        except Exception as primary_error:
            groq_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
            if not groq_key or groq_key.lower().startswith(("mock-", "test-", "mock_", "test_")):
                if _mock_mode():
                    return f"[Mocked Tier 4 Response for tests] {prompt[:50]}..."
                raise primary_error
            client = AsyncOpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1", timeout=45.0, max_retries=0)
            try:
                return await self._call_model(client, "llama-3.3-70b-versatile", prompt)
            except Exception:
                raise primary_error


router = LLMRouter()
