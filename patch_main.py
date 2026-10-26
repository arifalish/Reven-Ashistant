import re

with open('app/main.py', 'r') as f:
    content = f.read()

# Replace process_mission
new_process_mission = """async def process_mission(payload: dict):
    \"\"\"
    Background task to handle the full lifecycle of a mission.
    \"\"\"
    if "message" in payload and "text" in payload["message"]:
        chat_id = payload["message"]["chat"]["id"]
        text = payload["message"]["text"]

        # We may receive message_id from cloudflare worker, or we might need to send one ourselves
        message_id = payload.get("mission_control_message_id")

        if not message_id:
            message_id = await telegram_ux.send_message(
                chat_id=chat_id,
                text="🚀 **Live Mission Control Dashboard**\\n\\n⏳ Extracting intent and blueprinting strategy..."
            )
        else:
            await telegram_ux.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text="⏳ Extracting intent and blueprinting strategy..."
            )

        try:
            # Run the LangGraph Orchestrator (Phase 1, pauses at Phase 2)
            result_payload = await run_orchestrator(text, chat_id, message_id)

            if isinstance(result_payload, dict) and result_payload.get("type") == "credential_request":
                # Very rare in Phase 1, but technically possible if ingestion requested a credential.
                await telegram_ux.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text=result_payload.get("message")
                )
            else:
                # Standard HITL approval string
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✅ Approve & Launch All Agents", "callback_data": "approve_launch"}],
                        [{"text": "🎯 Edit Target City/Niche", "callback_data": "edit"}],
                        [{"text": "🛑 Cancel", "callback_data": "cancel"}]
                    ]
                }
                await telegram_ux.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text="⏳ Strategy Blueprint generated. Waiting for approval (Telegram HITL Gate)...\\nReply with inline buttons below.",
                    reply_markup=keyboard
                )

        except Exception as e:
            await telegram_ux.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text=f"❌ Error during execution: {str(e)}"
            )

    elif "callback_query" in payload:
        # Handle HITL inline button clicks
        callback = payload["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        data = callback["data"]
        message_id = callback["message"]["message_id"]

        if data.startswith("inject_api_key:"):
            _, service_name, actual_key = data.split(":", 2)
            await telegram_ux.update_status(chat_id, message_id, f"🔑 API Key received for {service_name}. Resuming agent execution...")
            resume_payload = {"api_key": actual_key}

        elif data == "approve_launch":
            await telegram_ux.update_status(chat_id, message_id, "✅ Launch approved! Starting Massive Parallel Swarm Execution...")
            resume_payload = {"action": "approve"}

        elif data == "edit":
            await telegram_ux.update_status(chat_id, message_id, "🔄 Editing Target City/Niche...")
            resume_payload = {"action": "edit", "modifications": "Updated Target City to NYC"}

        elif data == "cancel":
            await telegram_ux.update_status(chat_id, message_id, "🛑 Mission Cancelled.")
            resume_payload = {"action": "cancel"}

        else:
            return

        try:
            # Resume execution of the graph
            result_payload = await resume_orchestrator(chat_id, resume_payload)

            # Since orchestrator can yield zip bytes OR a credential interrupt dict payload:
            if isinstance(result_payload, bytes) and len(result_payload) > 0 and resume_payload.get("action") == "approve":
                await telegram_ux.send_document(
                    chat_id=chat_id,
                    document_bytes=result_payload,
                    filename="Agent_OS_Workspace.zip",
                    caption="✅ Mission Accomplished! Here is your structured workspace."
                )

                await telegram_ux.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text="✅ Mission Completed Successfully! Zip delivered."
                )
            elif isinstance(result_payload, dict) and result_payload.get("type") == "credential_request":
                # Handle the credential request interrupt sent back up from LangGraph
                service_name = result_payload.get("service_name")
                message = result_payload.get("message")
                await telegram_ux.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text=message
                )

        except Exception as e:
            await telegram_ux.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text=f"❌ Status: {str(e)}"
            )

    return"""

# Re-write the file
start_idx = content.find("async def process_mission")
if start_idx != -1:
    new_content = content[:start_idx] + new_process_mission
    with open('app/main.py', 'w') as f:
        f.write(new_content)
    print("Patched main.py")
else:
    print("Could not find process_mission")
