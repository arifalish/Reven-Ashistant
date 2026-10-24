import aiohttp
import io
import zipfile
from typing import Dict, Any, Optional
import json

class TelegramUX:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def update_status(self, chat_id: int, message_id: int, status_text: str):
        """
        Updates the pinned live mission control dashboard message.
        """
        if not message_id:
            return

        url = f"{self.base_url}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": f"🚀 **Live Mission Control Dashboard**\n\n{status_text}",
            "parse_mode": "Markdown"
        }

        async with aiohttp.ClientSession() as session:
            try:
                await session.post(url, json=payload)
            except Exception:
                pass

    async def send_document(self, chat_id: int, document_bytes: bytes, filename: str, caption: str = ""):
        """
        Sends the RAM ZIP Packager output to Telegram.
        """
        url = f"{self.base_url}/sendDocument"

        form = aiohttp.FormData()
        form.add_field('chat_id', str(chat_id))
        form.add_field('caption', caption)
        form.add_field('document', document_bytes, filename=filename, content_type='application/zip')

        async with aiohttp.ClientSession() as session:
            try:
                await session.post(url, data=form)
            except Exception:
                pass


def create_workspace_zip(artifacts: Dict[str, Any]) -> bytes:
    """
    Creates a structured .zip workspace entirely in RAM (io.BytesIO).
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, content in artifacts.items():
            if isinstance(content, dict):
                # Handle nested dict like replica_codebase/
                for sub_file, sub_content in content.items():
                    full_path = f"{filename}/{sub_file}"
                    zip_file.writestr(full_path, str(sub_content))
            else:
                zip_file.writestr(filename, str(content))

    zip_buffer.seek(0)
    return zip_buffer.read()
