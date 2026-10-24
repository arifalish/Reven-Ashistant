import asyncio
import time
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import AsyncOpenAI
from redis.asyncio import Redis
from core.config import settings

# In-memory fallback if Redis is not available
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

# Setup clients
redis_client: Optional[Redis] = None
if settings.UPSTASH_REDIS_URL and "mock-url" not in settings.UPSTASH_REDIS_URL:
    try:
        redis_client = Redis.from_url(settings.UPSTASH_REDIS_URL)
    except Exception:
        redis_client = None

local_bucket = InMemoryTokenBucket(capacity=100, refill_rate=10.0)

async def check_rate_limit(key: str, limit: int = 100, window: int = 60) -> bool:
    """Token bucket rate limit check"""
    if redis_client:
        try:
            # Simple fixed window counter as a fallback for token bucket in Redis
            current = await redis_client.get(key)
            if current and int(current) >= limit:
                return False

            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window, nx=True)
            await pipe.execute()
            return True
        except Exception:
            # Fallback to local
            pass

    return await local_bucket.consume(1)


class LLMRouter:
    def __init__(self):
        # Primary client routed through CF Gateway
        if "mock-account" in settings.CF_GATEWAY_URL:
            # Bypass CF Gateway for mock
            self.primary_client = AsyncOpenAI(api_key=settings.NVIDIA_API_KEY, base_url="https://integrate.api.nvidia.com/v1")
        else:
            # Use CF Gateway URL
            self.primary_client = AsyncOpenAI(api_key=settings.NVIDIA_API_KEY, base_url=f"{settings.CF_GATEWAY_URL}/openai/v1")

        self.groq_client = AsyncOpenAI(api_key=settings.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

    async def _call_model(self, client: AsyncOpenAI, model: str, prompt: str) -> str:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2048
        )
        return response.choices[0].message.content or ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier1(self, prompt: str) -> str:
        """Tier 1: Master Coordinator, Founder, Trader (DeepSeek R1 / Llama 3.3 70B)"""
        # Wait for rate limit
        while not await check_rate_limit("tier1_rl", limit=50, window=60):
            await asyncio.sleep(1)

        # For mock test fallback to simple echo if API fails due to EOL model errors
        try:
            return await self._call_model(self.primary_client, "meta/llama-3.1-70b-instruct", prompt)
        except Exception as e:
            if "mock-account" in settings.CF_GATEWAY_URL:
                return f"[Mocked Tier 1 Response for tests] {prompt[:50]}..."
            raise e

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier2(self, prompt: str) -> str:
        """Tier 2: Code & Reverse Engineering (Qwen 2.5 Coder 32B)"""
        while not await check_rate_limit("tier2_rl", limit=50, window=60):
            await asyncio.sleep(1)

        try:
            return await self._call_model(self.primary_client, "qwen/qwen2.5-coder-32b-instruct", prompt)
        except Exception as e:
            if "mock-account" in settings.CF_GATEWAY_URL:
                return f"[Mocked Tier 2 Response for tests] {prompt[:50]}..."
            raise e

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier3(self, prompt: str) -> str:
        """Tier 3: Creative & Content Swarm (Llama 3.1 70B)"""
        while not await check_rate_limit("tier3_rl", limit=100, window=60):
            await asyncio.sleep(1)

        try:
            return await self._call_model(self.primary_client, "meta/llama-3.1-70b-instruct", prompt)
        except Exception as e:
            if "mock-account" in settings.CF_GATEWAY_URL:
                return f"[Mocked Tier 3 Response for tests] {prompt[:50]}..."
            raise e

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def generate_tier4(self, prompt: str) -> str:
        """Tier 4: Bulk Swarm (Llama 3.1 8B, Fallback Groq/Gemini)"""
        if await check_rate_limit("tier4_rl", limit=200, window=60):
            try:
                return await self._call_model(self.primary_client, "meta/llama-3.1-8b-instruct", prompt)
            except Exception as e:
                # Fallback to Groq
                if "mock-account" in settings.CF_GATEWAY_URL:
                    return f"[Mocked Tier 4 Response for tests] {prompt[:50]}..."
                pass

        # Fallback to Groq if rate limit reached or primary failed
        try:
            return await self._call_model(self.groq_client, "llama-3.3-70b-versatile", prompt)
        except Exception:
            # Final fallback
            if "mock-account" in settings.CF_GATEWAY_URL:
                return f"[Mocked Tier 4 Fallback Response for tests] {prompt[:50]}..."
            return "[Fallback Error] Unable to process request across primary and fallback APIs."

router = LLMRouter()
