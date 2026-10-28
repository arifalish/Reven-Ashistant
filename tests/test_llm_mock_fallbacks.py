from core import llm_router


def test_mock_responses_are_limited_to_explicit_test_keys(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr(llm_router.settings, "NVIDIA_API_KEY", "test-nvidia")
    assert llm_router._mock_mode() is True

    monkeypatch.setattr(llm_router.settings, "NVIDIA_API_KEY", "mock-nvidia-key")
    assert llm_router._mock_mode() is True

    monkeypatch.setattr(llm_router.settings, "NVIDIA_API_KEY", "nvapi-real-production-key")
    assert llm_router._mock_mode() is False
