import re

with open('tests/test_smoke.py', 'r') as f:
    content = f.read()

# Update test to expect Markdown instead of ZIP
new_test = """
    # 1. Run orchestrator Phase 1 (Ingestion) -> should return interrupt value and pause at HITL
    print("\\n[Test] Running Phase 1 (Ingestion)...")
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
    assert "### 🎯 Sales & Leads" in res2
    assert "### 💻 Tech & MVP" in res2
"""

content = re.sub(r'    # 1. Run orchestrator Phase 1.*?assert "07_Replica_MVP_Codebase/index.html" in files', new_test, content, flags=re.DOTALL)

with open('tests/test_smoke.py', 'w') as f:
    f.write(content)
