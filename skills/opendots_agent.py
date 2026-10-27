import os
import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class OpenDotsWorkerInput(BaseModel):
    task: str = Field(description="The primary objective or task for the autonomous coworker.")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Shared context or state from the orchestrator.")

@tool("run_opendots_worker", args_schema=OpenDotsWorkerInput)
async def run_opendots_worker(task: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Acts as an autonomous, always-on coworker (OpenDots-inspired).
    Maintains internal reasoning to execute multi-step tasks, coordinating with
    the NVIDIA NIM LLM.
    """
    logger.info(f"Initiating OpenDots Coworker Task: {task}")

    api_key = os.getenv("NVIDIA_API_KEY", "mock-nvidia-key")
    model_name = os.getenv("NVIDIA_MODEL_NAME", "meta/llama-3.1-70b-instruct")

    # Configure the ChatOpenAI client pointing to NVIDIA NIM
    llm = ChatOpenAI(
        api_key=api_key,
        base_url="https://integrate.api.nvidia.com/v1",
        model=model_name,
        temperature=0.7,
        max_tokens=2048
    )

    system_prompt = (
        "You are an autonomous, proactive coworker agent. You have your own "
        "internal environment and maintain a log of your actions. You are given a task "
        "and must reason through it step-by-step. Provide a structured execution log "
        "and a final output."
    )

    user_prompt = f"Task: {task}"
    if context:
        user_prompt += f"\nContext: {json.dumps(context, indent=2)}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    try:
        # In a real OpenDots environment, this would involve a multi-agent loop or a ReAct agent.
        # For this tool, we simulate the coworker's internal processing via a structured LLM call.
        response = await llm.ainvoke(messages)

        result_dict = {
            "status": "completed",
            "task": task,
            "output": response.content,
            "execution_steps": ["Received task", "Analyzed context", "Generated response via NVIDIA NIM"]
        }
        return json.dumps(result_dict)
    except Exception as e:
        logger.error(f"OpenDots Coworker failed: {e}")
        return json.dumps({
            "status": "failed",
            "task": task,
            "error": str(e),
            "execution_steps": ["Received task", "Failed during execution"]
        })
