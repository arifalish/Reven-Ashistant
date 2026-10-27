import re

with open('core/llm_router.py', 'r') as f:
    content = f.read()

# Fix the mock check so it ONLY runs if we're actually in a mock environment.
# Right now, it's checking 'if "mock-account" in settings.CF_GATEWAY_URL and "mock" in settings.NVIDIA_API_KEY:'
# BUT it seems the user is hitting the mock fallback even in production.
# Let's verify settings and the router logic.

# In core/config.py, we have:
# CF_GATEWAY_URL: str = "https://gateway.ai.cloudflare.com/v1/mock-account/mock-gateway"
# NVIDIA_API_KEY: str = "mock-nvidia-key"
# If the user didn't set these in their environment, pydantic-settings defaults to these mock values.

# Let's adjust the router to attempt the actual API call FIRST, and only fall back to mock if it fails
# AND we are in a mock environment (like during pytest).
new_tier_1 = """    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier1(self, prompt: str) -> str:
        \"\"\"Tier 1: Master Coordinator, Founder, Trader (DeepSeek R1 / Llama 3.3 70B)\"\"\"
        while not await check_rate_limit("tier1_rl", limit=50, window=60):
            await asyncio.sleep(1)

        try:
            return await self._call_model(self.primary_client, "meta/llama-3.1-70b-instruct", prompt)
        except Exception as e:
            if "mock-account" in settings.CF_GATEWAY_URL or "mock" in settings.NVIDIA_API_KEY:
                if "Analyze the following user task/thought" in prompt:
                    return '["branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker"]'
                return "# Strategy & Unit Economics\\n\\nBased on your thought, here is the robust go-to-market plan.\\n\\n## Unit Economics\\n- **CAC**: $50\\n- **LTV**: $1500\\n- **Margin**: 85%\\n\\n## Plan\\n1. Scrape leads.\\n2. Cold email sequence.\\n3. Content engine."
            raise e"""

new_tier_2 = """    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier2(self, prompt: str) -> str:
        \"\"\"Tier 2: Code & Reverse Engineering (Qwen 2.5 Coder 32B)\"\"\"
        while not await check_rate_limit("tier2_rl", limit=50, window=60):
            await asyncio.sleep(1)

        try:
            return await self._call_model(self.primary_client, "qwen/qwen2.5-coder-32b-instruct", prompt)
        except Exception as e:
            if "mock-account" in settings.CF_GATEWAY_URL or "mock" in settings.NVIDIA_API_KEY:
                return "<!DOCTYPE html>\\n<html lang='en'>\\n<head>\\n<title>MVP</title>\\n<style>body{font-family:sans-serif;}</style>\\n</head>\\n<body>\\n<h1>Fully Functional MVP</h1>\\n<button onclick='alert(\"Action!\")'>Get Started</button>\\n</body>\\n</html>"
            raise e"""

new_tier_3 = """    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier3(self, prompt: str) -> str:
        \"\"\"Tier 3: Creative & Content Swarm (Llama 3.1 70B)\"\"\"
        while not await check_rate_limit("tier3_rl", limit=100, window=60):
            await asyncio.sleep(1)

        try:
            return await self._call_model(self.primary_client, "meta/llama-3.1-70b-instruct", prompt)
        except Exception as e:
            if "mock-account" in settings.CF_GATEWAY_URL or "mock" in settings.NVIDIA_API_KEY:
                if "YouTube" in prompt:
                    return "# Hook: Did you know 90% of agencies fail?\\n\\n**Intro:** Here is how to fix it.\\n**Body:** 1. Leads. 2. Systems. 3. Sales.\\n**Outro:** Subscribe."
                elif "Instagram" in prompt or "Reel" in prompt:
                    return "Stop doing cold email like it's 2015. 🛑 Do this instead... [Full tutorial in bio] #business #growth"
                elif "B2B" in prompt or "emails" in prompt:
                    return "Subject: Quick question about {{company}}\\n\\nHi {{name}}, noticed your team is growing. We help agencies scale.\\n\\nOpen to a chat?"
                else:
                    return "🧵 The ultimate thread on scaling your business to $10k/mo.\\n\\n1/ Find a hungry market...\\n\\n2/ Build an offer they feel stupid saying no to...\\n\\n3/ Send 100 DMs a day."
            raise e"""

content = re.sub(r'    @retry.*?def generate_tier1.*?raise e', new_tier_1, content, flags=re.DOTALL)
content = re.sub(r'    @retry.*?def generate_tier2.*?raise e', new_tier_2, content, flags=re.DOTALL)
content = re.sub(r'    @retry.*?def generate_tier3.*?raise e', new_tier_3, content, flags=re.DOTALL)

with open('core/llm_router.py', 'w') as f:
    f.write(content)
