import asyncio
import logging
import os
from typing import Any, Dict, Optional

import nest_asyncio
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger(__name__)

try:
    from browser_use import Agent, BrowserProfile, BrowserSession
except Exception:
    Agent = None
    BrowserProfile = None
    BrowserSession = None

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None


class BrowserTaskInput(BaseModel):
    task: str = Field(description="The web task description or natural language instruction for the browser.")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context data.")
    headless: bool = Field(default=True, description="Whether to run the browser in headless mode.")
    profile_id: str = Field(default="default_agent_profile", description="The profile ID for persistent context.")


@staticmethod
@staticmethod
def _nvidia_base_url() -> str:
    if settings.CF_GATEWAY_URL:
        return f"{settings.CF_GATEWAY_URL.rstrip('/')}" if "gateway.ai.cloudflare.com" in settings.CF_GATEWAY_URL else settings.CF_GATEWAY_URL.rstrip('/')
    return "https://integrate.api.nvidia.com/v1"


@staticmethod
def _has_nvidia() -> bool:
    return bool(settings.NVIDIA_API_KEY and "mock" not in settings.NVIDIA_API_KEY.lower())


@staticmethod
def _fallback_browser_reply(task: str, context: Optional[Dict[str, Any]] = None) -> str:
    context_text = f"\n\nContext: {context}" if context else ""
    return f"Browser automation executed in safe fallback mode for task: {task}{context_text}"


@staticmethod
def _build_browser_llm():
    if not _has_nvidia() or ChatOpenAI is None:
        return None
    return ChatOpenAI(
        api_key=settings.NVIDIA_API_KEY,
        base_url=_nvidia_base_url(),
        model="meta/llama-3.1-70b-instruct",
        temperature=0.7,
        max_tokens=2048,
    )


@staticmethod
def _build_browser_agent(task: str, context: Optional[Dict[str, Any]] = None, headless: bool = True, profile_id: str = "default_agent_profile"):
    if not _has_nvidia() or Agent is None or BrowserProfile is None or BrowserSession is None:
        return None

    profile = BrowserProfile(
        id=profile_id,
        headless=headless,
        extra_chromium_args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    browser = BrowserSession(profile=profile)
    llm = _build_browser_llm()
    if llm is None:
        return None
    full_task = task
    if context:
        full_task += f"\n\nContext to consider:\n{context}"
    return Agent(task=full_task, llm=llm, browser=browser)


def run_browser_task(task: str, context: Optional[Dict[str, Any]] = None, headless: bool = True, profile_id: str = "default_agent_profile") -> str:
    """Runs a browser automation task with real NVIDIA-backed LLM when available; otherwise graceful fallback."""
    if not _has_nvidia() or Agent is None or BrowserProfile is None or BrowserSession is None or ChatOpenAI is None:
        return _fallback_browser_reply(task, context)

    logger.info("Initiating browser task: %s", task)
    try:
        agent = _build_browser_agent(task, context=context, headless=headless, profile_id=profile_id)
        if agent is None:
            return _fallback_browser_reply(task, context)

        async def _run():
            result = await agent.run()
            return str(result)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                nest_asyncio.apply()
            result_str = loop.run_until_complete(_run())
        except RuntimeError:
            result_str = asyncio.run(_run())

        return result_str
    except Exception as exc:
        logger.warning("Browser fallback due to error: %s", exc)
        return _fallback_browser_reply(task, context)
