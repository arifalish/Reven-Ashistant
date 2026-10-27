import asyncio
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse
import json

from core.config import settings
from core.orchestrator_graph import run_orchestrator, resume_orchestrator
from interfaces.telegram_bot import TelegramBot

app = FastAPI(title="Autonomous Multi-Agent OS", version="1.0.0")

telegram_bot = TelegramBot(settings.TELEGRAM_BOT_TOKEN)

@app.get("/")
async def root():
    return {"status": "Agent-OS is running. Waiting for missions."}

@app.post("/api/v1/callback/scraper")
async def scraper_callback(request: Request, background_tasks: BackgroundTasks):
    """
    Async Webhook Callback for google-maps-scraper-kit
    Receives CSV leads, injects into BlackboardState, and triggers sales-desk-skill.
    """
    secret = request.headers.get("X-Webhook-Secret")
    if secret != settings.API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    mission_id = payload.get("mission_id")
    csv_data = payload.get("csv_data")

    if not mission_id or not csv_data:
        raise HTTPException(status_code=400, detail="Missing mission_id or csv_data")

    background_tasks.add_task(process_scraper_callback, mission_id, csv_data)

    return {"status": "accepted"}

async def process_scraper_callback(mission_id: str, csv_data: str):
    """Background task to update state and trigger sales generation"""
    from core.blackboard_memory import memory_manager
    from core.llm_router import router
    from core.skill_loader import skill_registry

    state = await memory_manager.load_state(mission_id)
    if not state.mission_id:
        return # Mission not found

    state.leads_csv = csv_data

    # Trigger sales desk skill logic
    strategy = state.founder_strategy.get('summary', '')
    b2b_prompt = f"Write personalized B2B cold emails and LinkedIn DMs based on strategy: {strategy}\\nLeads: {csv_data[:1000]}"
    emails = await router.generate_tier3(b2b_prompt)

    state.b2b_emails = [emails]
    await memory_manager.save_state(state)

    # Notify user if needed (omitted for brevity, assume handled by graph aggregator)


@app.post("/api/v1/orchestrate")
async def orchestrate(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint receiving webhooks forwarded from Edge/Cloudflare Worker.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Process asynchronously to free up the request immediately
    background_tasks.add_task(process_mission, payload)

    return {"status": "Mission accepted"}

async def process_mission(payload: dict):
    """
    Background task to handle the full lifecycle of a mission.
    """
    if "message" in payload and "text" in payload["message"]:
        chat_id = payload["message"]["chat"]["id"]
        text = payload["message"]["text"]

        # We may receive message_id from cloudflare worker, or we might need to send one ourselves
        message_id = payload.get("mission_control_message_id")

        if not message_id:
            message_id = await telegram_bot.send_message(
                chat_id=chat_id,
                text="🚀 **Live Mission Control Dashboard**\n\n⏳ Extracting intent and blueprinting strategy..."
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


            if isinstance(result_payload, dict) and result_payload.get("type") == "credential_request":
                # Very rare in Phase 1, but technically possible if ingestion requested a credential.
                await telegram_bot.update_status(
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
                await telegram_bot.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text="⏳ Strategy Blueprint generated. Waiting for approval (Telegram HITL Gate)...\nReply with inline buttons below.",
                    reply_markup=keyboard
                )

        except Exception as e:
            await telegram_bot.update_status(
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
            await telegram_bot.update_status(chat_id, message_id, f"🔑 API Key received for {service_name}. Resuming agent execution...")
            resume_payload = {"api_key": actual_key}

        elif data == "approve_launch":
            await telegram_bot.update_status(chat_id, message_id, "✅ Launch approved! Starting Massive Parallel Swarm Execution...")
            resume_payload = {"action": "approve"}

        elif data == "edit":
            await telegram_bot.update_status(chat_id, message_id, "🔄 Editing Target City/Niche...")
            resume_payload = {"action": "edit", "modifications": "Updated Target City to NYC"}

        elif data == "cancel":
            await telegram_bot.update_status(chat_id, message_id, "🛑 Mission Cancelled.")
            resume_payload = {"action": "cancel"}

        else:
            return

        async def resume_callback(status: str):
            await telegram_bot.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text=f"⚙️ {status}"
            )

        try:
            # Resume execution of the graph
            result_payload = await resume_orchestrator(chat_id, resume_payload, resume_callback)

            # Since orchestrator can yield final report string OR a credential interrupt dict payload:
            if isinstance(result_payload, str) and len(result_payload) > 0 and resume_payload.get("action") == "approve":
                # Send the final Markdown report directly to chat
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=result_payload
                )

                await telegram_bot.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text="✅ Mission Completed Successfully! Report delivered."
                )
            elif isinstance(result_payload, dict) and result_payload.get("type") == "credential_request":
                # Handle the credential request interrupt sent back up from LangGraph
                service_name = result_payload.get("service_name")
                message = result_payload.get("message")
                await telegram_bot.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text=message
                )

        except Exception as e:
            await telegram_bot.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text=f"❌ Status: {str(e)}"
            )

    return