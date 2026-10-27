"""Configure Telegram's webhook from Render's runtime URL, then start FastAPI."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def configure_webhook() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    base_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

    if not token or token.startswith("mock-"):
        print("Telegram webhook skipped: set a real TELEGRAM_BOT_TOKEN in Render.")
        return
    if not base_url:
        print("Telegram webhook skipped: RENDER_EXTERNAL_URL is unavailable; configure it manually.")
        return

    payload = {
        "url": f"{base_url}/api/v1/orchestrate",
        "drop_pending_updates": False,
    }
    if secret:
        payload["secret_token"] = secret

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/setWebhook",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("ok"):
            print(f"Telegram webhook configured: {payload['url']}")
        else:
            print(f"WARNING: Telegram rejected setWebhook: {result.get('description', 'unknown error')}")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"WARNING: Telegram webhook auto-configuration failed: {exc}")


if __name__ == "__main__":
    configure_webhook()
    port = os.getenv("PORT", "8000")
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
    )
