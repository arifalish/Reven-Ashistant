with open('tests/test_smoke.py', 'r') as f:
    content = f.read()

# Since our test supervisor uses the mock router, the mock router returns the default strategy markdown instead of a JSON list of nodes.
# Let's fix the mock response in llm_router.py for generate_tier1 to properly return a JSON node list if it sees "Analyze the following user task/thought"

new_test = """
    # 1. Run orchestrator Phase 1 (Ingestion) -> should return interrupt value and pause at HITL
    print("\\n[Test] Running Phase 1 (Ingestion)...")
    res1 = await run_orchestrator(raw_thought, chat_id, message_id)
    assert res1 == "Please approve the strategy via Telegram callback.", "Initial run should return interrupt string"
"""

# Let's just fix llm_router first
