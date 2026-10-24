import asyncio
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse
import json

from core.config import settings
from core.orchestrator_graph import run_orchestrator, resume_orchestrator
from delivery.telegram_ux import TelegramUX

app = FastAPI(title="Autonomous Multi-Agent OS", version="1.0.0")

telegram_ux = TelegramUX(settings.TELEGRAM_BOT_TOKEN)

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
        message_id = payload.get("mission_control_message_id")

        # Initial status update
        await telegram_ux.update_status(
            chat_id=chat_id,
            message_id=message_id,
            status_text="⏳ Extracting intent and blueprinting strategy..."
        )

        try:
            # Run the LangGraph Orchestrator (Phase 1, pauses at Phase 2)
            await run_orchestrator(text, chat_id, message_id)

            # Update status to waiting for approval
            await telegram_ux.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text="⏳ Strategy Blueprint generated. Waiting for approval (Telegram HITL Gate)...\\nReply with inline button [✅ Approve & Launch All Agents], [🎯 Edit Target City/Niche], or [🛑 Cancel]."
            )

            # In a real telegram bot, we would attach actual Inline Keyboard Buttons here

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

        if data == "approve_launch":
            await telegram_ux.update_status(chat_id, message_id, "✅ Launch approved! Starting Massive Parallel Swarm Execution...")
            resume_payload = {"action": "approve"}

        elif data == "edit":
            # Real bot would prompt for text and send another callback
            # We mock the edited payload for this architecture
            await telegram_ux.update_status(chat_id, message_id, "🔄 Editing Target City/Niche...")
            resume_payload = {"action": "edit", "modifications": "Updated Target City to NYC"}

        elif data == "cancel":
            await telegram_ux.update_status(chat_id, message_id, "🛑 Mission Cancelled.")
            resume_payload = {"action": "cancel"}

        else:
            return

        try:
            # Resume execution of the graph
            result_zip_bytes = await resume_orchestrator(chat_id, resume_payload)

            if result_zip_bytes and resume_payload["action"] == "approve":
                await telegram_ux.send_document(
                    chat_id=chat_id,
                    document_bytes=result_zip_bytes,
                    filename="Agent_OS_Workspace.zip",
                    caption="✅ Mission Accomplished! Here is your structured workspace."
                )

                await telegram_ux.update_status(
                    chat_id=chat_id,
                    message_id=message_id,
                    status_text="✅ Mission Completed Successfully! Zip delivered."
                )
        except Exception as e:
            await telegram_ux.update_status(
                chat_id=chat_id,
                message_id=message_id,
                status_text=f"❌ Status: {str(e)}"
            )

    return
