import asyncio
import time
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential
from openai import AsyncOpenAI
from redis.asyncio import Redis

from core.config import settings


def _mock_mode() -> bool:
    """Allow canned responses only for explicit mock/test keys, never real deployments."""
    key = (settings.NVIDIA_API_KEY or "").strip().lower()
    return key.startswith(("mock-", "test-", "mock_", "test_"))


class InMemoryTokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()

    async def consume(self, tokens: int = 1) -> bool:
        now = time.time()
        time_passed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
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
        if "mock-account" in settings.CF_GATEWAY_URL:
            self.primary_client = AsyncOpenAI(
                api_key=settings.NVIDIA_API_KEY,
                base_url="https://integrate.api.nvidia.com/v1",
            )
        else:
            self.primary_client = AsyncOpenAI(
                api_key=settings.NVIDIA_API_KEY,
                base_url=f"{settings.CF_GATEWAY_URL}/openai/v1",
            )
        self.groq_client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )

    async def _call_model(self, client: AsyncOpenAI, model: str, prompt: str) -> str:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier1(self, prompt: str) -> str:
        """Master coordination, founder strategy and supervisor routing."""
        while not await check_rate_limit("tier1_rl", limit=50, window=60):
            await asyncio.sleep(1)
        try:
            return await self._call_model(
                self.primary_client, "meta/llama-3.3-70b-instruct", prompt
            )
        except Exception:
            if _mock_mode():
                if "Analyze the following user task/thought" in prompt:
                    return '["branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker"]'
                return (
                    "# Strategy & Unit Economics\n\n"
                    "Mock strategy for tests only.\n\n"
                    "## Plan\n1. Validate the request.\n2. Execute configured skills.\n3. Report verified outcomes."
                )
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier2(self, prompt: str) -> str:
        """Code and reverse-engineering tier."""
        while not await check_rate_limit("tier2_rl", limit=50, window=60):
            await asyncio.sleep(1)
        try:
            return await self._call_model(
                self.primary_client, "qwen/qwen2.5-coder-32b-instruct", prompt
            )
        except Exception:
            if _mock_mode():
                return (
                    "<!DOCTYPE html><html lang='en'><head><title>Test MVP</title></head>"
                    "<body><h1>Mock response for tests only</h1></body></html>"
                )
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier3(self, prompt: str) -> str:
        """Creative and content generation tier."""
        while not await check_rate_limit("tier3_rl", limit=100, window=60):
            await asyncio.sleep(1)
        try:
            return await self._call_model(
                self.primary_client, "meta/llama-3.1-70b-instruct", prompt
            )
        except Exception:
            if _mock_mode():
                if "YouTube" in prompt:
                    return "# Test Hook\n\nMock YouTube draft for automated tests."
                if "Instagram" in prompt or "Reel" in prompt:
                    return "Mock Instagram draft for automated tests."
                if "B2B" in prompt or "emails" in prompt:
                    return "Subject: Test only\n\nMock outreach draft for automated tests."
                return "Mock content draft for automated tests."
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def generate_tier4(self, prompt: str) -> str:
        """Bulk generation tier with Groq fallback."""
        if await check_rate_limit("tier4_rl", limit=200, window=60):
            try:
                return await self._call_model(
                    self.primary_client, "meta/llama-3.1-8b-instruct", prompt
                )
            except Exception:
                if _mock_mode():
                    return f"[Mocked Tier 4 Response for tests] {prompt[:50]}..."
        try:
            return await self._call_model(
                self.groq_client, "llama-3.3-70b-versatile", prompt
            )
        except Exception:
            if _mock_mode():
                return f"[Mocked Tier 4 Fallback Response for tests] {prompt[:50]}..."
            return "[Fallback Error] Unable to process request across primary and fallback APIs."


router = LLMRouter()
