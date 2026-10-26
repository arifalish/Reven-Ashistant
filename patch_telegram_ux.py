import re

with open('delivery/telegram_ux.py', 'r') as f:
    content = f.read()

# Add send_message method
send_message_code = """
    async def send_message(self, chat_id: int, text: str, reply_markup: Optional[Dict] = None) -> Optional[int]:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
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

content = content.replace('    async def update_status(self, chat_id: int, message_id: int, status_text: str):', send_message_code)

# Add reply_markup to update_status payload
update_status_payload = """        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": f"🚀 **Live Mission Control Dashboard**\\n\\n{status_text}",
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup"""

content = re.sub(r'        payload = \{[^}]+\}', update_status_payload, content, flags=re.MULTILINE)

with open('delivery/telegram_ux.py', 'w') as f:
    f.write(content)
print("Patched telegram_ux.py")
