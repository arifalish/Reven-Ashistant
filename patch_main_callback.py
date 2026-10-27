import re

with open('app/main.py', 'r') as f:
    content = f.read()

# Add callback functions inside process_mission
new_mission = """async def process_mission(payload: dict):
    \"\"\"
    Background task to handle the full lifecycle of a mission.
    \"\"\"
    if "message" in payload and "text" in payload["message"]:
        chat_id = payload["message"]["chat"]["id"]
        text = payload["message"]["text"]

        # We may receive message_id from cloudflare worker, or we might need to send one ourselves
        message_id = payload.get("mission_control_message_id")

        if not message_id:
            message_id = await telegram_bot.send_message(
                chat_id=chat_id,
                text="🚀 **Live Mission Control Dashboard**\\n\\n⏳ Extracting intent and blueprinting strategy..."
            )
        else:
            await telegram_bot.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text="⏳ Extracting intent and blueprinting strategy..."
            )

        async def status_callback(status: str):
            await telegram_bot.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text=f"⏳ {status}"
            )

        try:
            # Run the LangGraph Orchestrator (Phase 1, pauses at Phase 2)
            result_payload = await run_orchestrator(text, chat_id, message_id, status_callback)
"""

content = re.sub(r'async def process_mission\(payload: dict\):.*?result_payload = await run_orchestrator\(text, chat_id, message_id\)', new_mission, content, flags=re.DOTALL)

new_resume = """        async def resume_callback(status: str):
            await telegram_bot.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text=f"⚙️ {status}"
            )

        try:
            # Resume execution of the graph
            result_payload = await resume_orchestrator(chat_id, resume_payload, resume_callback)"""

content = re.sub(r'        try:\n            # Resume execution of the graph\n            result_payload = await resume_orchestrator\(chat_id, resume_payload\)', new_resume, content, flags=re.DOTALL)


with open('app/main.py', 'w') as f:
    f.write(content)
