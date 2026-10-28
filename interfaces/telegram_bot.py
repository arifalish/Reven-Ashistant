import aiohttp
from typing import Dict, Any, Optional

class TelegramBot:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: int, text: str, reply_markup: Optional[Dict] = None) -> Optional[int]:
        """
        Sends a new message to Telegram and returns the message ID.
        """
        url = f"{self.base_url}/sendMessage"

        # Max message length in Telegram is 4096. Truncate if necessary.
        if len(text) > 4096:
            text = text[:4093] + "..."

        payload = {
            "chat_id": chat_id,
            "text": text
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result", {}).get("message_id")
            except Exception:
                pass
        return None

    async def update_status(self, chat_id: int, message_id: int, status_text: str, reply_markup: Optional[Dict] = None):
        """
        Updates a specific message (e.g. status tracking).
        """
        if not message_id:
            return

        url = f"{self.base_url}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": f"🚀 Reven Assistant\n\n{status_text}"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with aiohttp.ClientSession() as session:
            try:
                await session.post(url, json=payload)
            except Exception:
                pass
