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

    # Need to pre-fill the vault so node_branch_c_tech doesn't interrupt during resume
    import os
    os.environ["VERCEL_TOKEN"] = "mocked-vercel-token"


    # 1. Run orchestrator Phase 1 (Ingestion) -> should return interrupt value and pause at HITL
    print("\n[Test] Running Phase 1 (Ingestion)...")
    res1 = await run_orchestrator(raw_thought, chat_id, message_id)
    assert res1 == "Please approve the strategy via Telegram callback.", "Initial run should return interrupt string"

    # 2. Resume with Approval (Phase 3 & 4)
    print("[Test] Resuming with Approval payload...")
    resume_payload = {"action": "approve"}
    res2 = await resume_orchestrator(chat_id, resume_payload)

    # 3. Verify final_report output
    assert res2 is not None and len(res2) > 0, "Resume should return a string payload"
    assert isinstance(res2, str), f"Expected str but got {type(res2)}: {res2}"

    print(f"[Test] Final Report length: {len(res2)}")
    assert "### 🧠 Master Strategy" in res2
    assert "### 🗂️ Supervisor Execution Plan" in res2
    assert "### 🤖 Specialized Skill Results" in res2



    print("[Test] Smoke test complete!")

@pytest.mark.asyncio
async def test_credential_vault_encryption():
    from core.credential_vault import credential_vault

    test_key = "secret_api_key_12345"
    encrypted = credential_vault.encrypt(test_key)

    assert encrypted != test_key
    assert isinstance(encrypted, str)

    decrypted = credential_vault.decrypt(encrypted)
    assert decrypted == test_key

@pytest.mark.asyncio
async def test_credential_vault_interrupt_flow():
    from core.blackboard_memory import BlackboardState
    from core.credential_vault import credential_vault
    import os

    state = BlackboardState(mission_id="test-vault")

    # Reset env for test predictability
    if "TEST_SERVICE_KEY" in os.environ:
        del os.environ["TEST_SERVICE_KEY"]

    # Mocking interrupt is tricky outside of runnable context.
    # Instead, we just mock the actual interrupt call in the credential_vault
    import core.credential_vault
    original_interrupt = core.credential_vault.interrupt
    core.credential_vault.interrupt = lambda payload: {"api_key": "user_provided_key_from_telegram"}

    try:
        acquired_key = credential_vault.get_or_request_credential(
            state, "TestService", "TEST_SERVICE_KEY", "https://example.com/api"
        )

        assert acquired_key == "user_provided_key_from_telegram"
        assert os.environ.get("TEST_SERVICE_KEY") == "user_provided_key_from_telegram"

        # Verify it saved to vault
        assert "TestService" in state.vault_data
        decrypted_vault_key = credential_vault.decrypt(state.vault_data["TestService"])
        assert decrypted_vault_key == "user_provided_key_from_telegram"

    finally:
        # Restore interrupt
        core.credential_vault.interrupt = original_interrupt
