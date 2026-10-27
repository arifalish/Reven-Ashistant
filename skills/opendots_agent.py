import json
import logging
import os
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger(__name__)

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None


class OpenDotsWorkerInput(BaseModel):
    task: str = Field(description="The primary objective or task for the autonomous coworker.")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Shared context from the orchestrator.")


def _has_nvidia() -> bool:
    return bool(settings.NVIDIA_API_KEY and "mock" not in settings.NVIDIA_API_KEY.lower())


def _nvidia_base_url() -> str:
    if settings.CF_GATEWAY_URL:
        return settings.CF_GATEWAY_URL.rstrip("/")
    return "https://integrate.api.nvidia.com/v1"


@tool("run_opendots_worker", args_schema=OpenDotsWorkerInput)
async def run_opendots_worker(task: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Runs an autonomous coworker task using NVIDIA when configured; otherwise returns a structured fallback."""
    logger.info("Initiating OpenDots coworker task: %s", task)

    if not _has_nvidia() or ChatOpenAI is None:
        return json.dumps({
            "status": "completed",
            "task": task,
            "output": "OpenDots worker ran in safe fallback mode.",
            "execution_steps": ["Received task", "Executed fallback workflow"],
        })

    llm = ChatOpenAI(
        api_key=settings.NVIDIA_API_KEY,
        base_url=_nvidia_base_url(),
        model=os.getenv("NVIDIA_MODEL_NAME", "meta/llama-3.1-70b-instruct"),
        temperature=0.7,
        max_tokens=2048,
    )

    system_prompt = (
        "You are an autonomous, proactive coworker agent. "
        "You have your own internal environment and maintain a log of actions. "
        "You are given a task and must reason through it step by step."
    )
    user_prompt = f"Task: {task}"
    if context:
        user_prompt += f"\nContext: {json.dumps(context, indent=2)}"

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    try:
        response = await llm.ainvoke(messages)
        return json.dumps({
            "status": "completed",
            "task": task,
            "output": response.content,
            "execution_steps": ["Received task", "Analyzed context", "Generated response via NVIDIA NIM"],
        })
    except Exception as exc:
        logger.error("OpenDots worker failed: %s", exc)
        return json.dumps({
            "status": "failed",
            "task": task,
            "error": str(exc),
            "execution_steps": ["Received task", "Failed during execution"],
        })
