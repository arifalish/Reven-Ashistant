import re
with open('app/main.py', 'r') as f:
    content = f.read()

# Update import
content = content.replace("from delivery.telegram_ux import TelegramUX", "from interfaces.telegram_bot import TelegramBot")
content = content.replace("telegram_ux = TelegramUX(settings.TELEGRAM_BOT_TOKEN)", "telegram_bot = TelegramBot(settings.TELEGRAM_BOT_TOKEN)")

# Replace telegram_ux instances
content = content.replace("telegram_ux.send_message", "telegram_bot.send_message")
content = content.replace("telegram_ux.update_status", "telegram_bot.update_status")

# Update resume_orchestrator handling to send message instead of zip document
new_resume_handling = """            # Since orchestrator can yield final report string OR a credential interrupt dict payload:
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
                )"""

content = re.sub(r'            # Since orchestrator can yield zip bytes OR a credential interrupt dict payload:.*?status_text="✅ Mission Completed Successfully! Zip delivered."\n                \)', new_resume_handling, content, flags=re.DOTALL)

with open('app/main.py', 'w') as f:
    f.write(content)
