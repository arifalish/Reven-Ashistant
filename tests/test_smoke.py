import pytest
import asyncio
import os
import io
import zipfile

# Mock environment variables before importing anything
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["NVIDIA_API_KEY"] = "test-nvidia"
os.environ["CF_GATEWAY_URL"] = "https://gateway.ai.cloudflare.com/v1/mock-account/mock-gateway"

# Import all core modules to ensure no circular dependencies
from app.main import app
from core.config import settings
from core.llm_router import router
from core.blackboard_memory import memory_manager
from core.skill_loader import skill_registry
from core.orchestrator_graph import run_orchestrator, resume_orchestrator

@pytest.mark.asyncio
async def test_end_to_end_orchestrator():
    chat_id = 12345
    message_id = 67890
    raw_thought = "I want to start a plumbing business in San Francisco."

    # 1. Run orchestrator Phase 1 (Ingestion) -> should return empty bytes and pause at HITL
    print("\\n[Test] Running Phase 1 (Ingestion)...")
    res1 = await run_orchestrator(raw_thought, chat_id, message_id)
    assert res1 == b"", "Initial run should return empty bytes because it pauses at HITL"

    # 2. Resume with Approval (Phase 3 & 4)
    print("[Test] Resuming with Approval payload...")
    resume_payload = {"action": "approve"}
    res2 = await resume_orchestrator(chat_id, resume_payload)

    # 3. Verify ZIP output
    assert res2 is not None and len(res2) > 0, "Resume should return a ZIP byte payload"

    # Unzip in memory to verify structure
    zip_buffer = io.BytesIO(res2)
    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        files = zip_file.namelist()
        print(f"[Test] ZIP contents: {files}")
        assert "01_Founder_Strategy_and_Unit_Economics.md" in files
        assert "04_YouTube_Scripts_and_Scored_Hooks.md" in files
        assert "07_Replica_MVP_Codebase/index.html" in files

    print("[Test] Smoke test complete!")
