import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from browser_use import Agent, BrowserProfile, BrowserSession
import logging

logger = logging.getLogger(__name__)

class BrowserTaskInput(BaseModel):
    task: str = Field(description="The web task description or natural language instruction for the browser.")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context or state data to use in the task.")
    headless: bool = Field(default=True, description="Whether to run the browser in headless mode.")
    profile_id: str = Field(default="default_agent_profile", description="The profile ID for persistent context.")

@tool("run_browser_task", args_schema=BrowserTaskInput)
def run_browser_task(task: str, context: Optional[Dict[str, Any]] = None, headless: bool = True, profile_id: str = "default_agent_profile") -> str:
    """
    Executes a given natural language browser task autonomously using browser-use.
    Maintains persistent state between actions if the same profile_id is used.
    """
    logger.info(f"Initiating browser task: {task} (headless={headless}, profile={profile_id})")
    try:
        # Create persistent profile
        profile = BrowserProfile(
            id=profile_id,
            headless=headless,
            extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        # Create browser session
        browser = BrowserSession(profile=profile)

        # Initialize LLM model - we default to standard OpenAI chat but can be customized
        llm = ChatOpenAI(model="gpt-4o") # Using 4o since browser-use works best with vision-capable models

        # Build task string including context if provided
        full_task = task
        if context:
            full_task += f"\n\nContext to consider:\n{context}"

        # Initialize agent
        agent = Agent(
            task=full_task,
            llm=llm,
            browser=browser
        )

        # We need an event loop to run the async agent.run() method from this sync tool
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already inside a running loop, we shouldn't block.
            # But LangGraph usually runs tools synchronously unless wrapped in async.
            # Ideally this tool should be async, but for tool node compatibility we'll use a new loop if needed.
            # We'll use a standard approach for sync execution of async functions in tools.
            pass

        async def _run():
            result = await agent.run()
            # result is an AgentHistoryList
            return str(result)

        try:
            # Try getting current loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            result_str = loop.run_until_complete(_run())
        except RuntimeError:
            result_str = asyncio.run(_run())

        # Clean up browser
        async def _close():
            await browser.close()

        try:
            asyncio.run(_close())
        except Exception as e:
             logger.warning(f"Error closing browser: {e}")

        return result_str

    except Exception as e:
        logger.error(f"Failed to execute browser task: {e}")
        return f"Error executing browser task: {str(e)}"
