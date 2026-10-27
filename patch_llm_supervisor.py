import re

with open('core/llm_router.py', 'r') as f:
    content = f.read()

new_tier_1 = """    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_tier1(self, prompt: str) -> str:
        \"\"\"Tier 1: Master Coordinator, Founder, Trader (DeepSeek R1 / Llama 3.3 70B)\"\"\"
        while not await check_rate_limit("tier1_rl", limit=50, window=60):
            await asyncio.sleep(1)

        try:
            if "mock-account" in settings.CF_GATEWAY_URL and "mock" in settings.NVIDIA_API_KEY:
                if "Analyze the following user task/thought" in prompt:
                    return '["branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker"]'
                return "# Strategy & Unit Economics\\n\\nBased on your thought, here is the robust go-to-market plan.\\n\\n## Unit Economics\\n- **CAC**: $50\\n- **LTV**: $1500\\n- **Margin**: 85%\\n\\n## Plan\\n1. Scrape leads.\\n2. Cold email sequence.\\n3. Content engine."
            return await self._call_model(self.primary_client, "meta/llama-3.1-70b-instruct", prompt)
        except Exception as e:
            if "mock-account" in settings.CF_GATEWAY_URL:
                if "Analyze the following user task/thought" in prompt:
                    return '["branch_a_sales", "branch_b_content", "branch_c_tech", "branch_d_coworker"]'
                return "# Strategy & Unit Economics\\n\\nBased on your thought, here is the robust go-to-market plan.\\n\\n## Unit Economics\\n- **CAC**: $50\\n- **LTV**: $1500\\n- **Margin**: 85%\\n\\n## Plan\\n1. Scrape leads.\\n2. Cold email sequence.\\n3. Content engine."
            raise e"""

content = re.sub(r'    @retry.*?def generate_tier1.*?raise e', new_tier_1, content, flags=re.DOTALL)

with open('core/llm_router.py', 'w') as f:
    f.write(content)
