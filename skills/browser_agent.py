import os
import asyncio
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from browser_use.agent.service import Agent
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile
from core.config import settings

@tool
async def run_browser_task(task_description: str) -> str:
    """
    Executes a complex web action asynchronously using an autonomous browser agent.
    Use this tool for web scraping, navigating dynamic single-page applications,
    or performing authenticated actions like posting to social media.
    """
    try:
        # We define a persistent browser context to retain sessions and avoid 2FA on repeat visits
        profile = BrowserProfile(
            headless=True,
            extra_chromium_args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                f"--user-data-dir={os.path.abspath('./browser_data')}"
            ]
        )
        browser = BrowserSession(profile=profile)

        # We attach the router's base model (or directly configure a ChatOpenAI for browser-use)
        # Using the standard configuration that routes via CF AI Gateway or direct Nvidia/OpenAI
        base_url = f"{settings.CF_GATEWAY_URL}/openai/v1" if "mock-account" not in settings.CF_GATEWAY_URL else "https://api.openai.com/v1"
        api_key = settings.NVIDIA_API_KEY if "mock-account" not in settings.CF_GATEWAY_URL else "mock-key"

        # Typically browser-use works best with high-tier reasoning models like GPT-4o or Claude 3.5.
        # Using Llama 3.3 70B as configured in this OS.
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model="meta/llama-3.1-70b-instruct",
            temperature=0.0
        )

        # Initialize the autonomous agent with the objective
        agent = Agent(
            task=task_description,
            llm=llm,
            browser=browser
        )

        # Run the agent
        history = await agent.run()

        await browser.close()

        return str(history.final_result())
    except Exception as e:
        return f"Browser Execution Error: {str(e)}"
