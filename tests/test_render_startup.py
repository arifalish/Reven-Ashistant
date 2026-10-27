import json

from scripts import start


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"ok": True, "result": True}).encode("utf-8")


def test_render_startup_sets_telegram_webhook_and_secret(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:real-looking-token")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://reven.example.onrender.com/")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "render-secret")
    monkeypatch.setattr(start.urllib.request, "urlopen", fake_urlopen)

    start.configure_webhook()

    assert captured["url"] == "https://api.telegram.org/bot123456:real-looking-token/setWebhook"
    assert captured["timeout"] == 20
    assert captured["payload"] == {
        "url": "https://reven.example.onrender.com/api/v1/orchestrate",
        "drop_pending_updates": False,
        "secret_token": "render-secret",
    }


def test_render_startup_skips_mock_telegram_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock-telegram-token")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://reven.example.onrender.com")
    monkeypatch.setattr(
        start.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call Telegram")),
    )

    start.configure_webhook()
