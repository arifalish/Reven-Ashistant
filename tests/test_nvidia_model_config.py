import inspect

from core import llm_router


def test_model_failover_list_has_multiple_current_candidates():
    assert len(llm_router.FALLBACK_MODELS) >= 3
    assert "nvidia/deepseek-v4.1-flash" in llm_router.FALLBACK_MODELS
    source = inspect.getsource(llm_router.LLMRouter)
    assert "models.list()" in source
    assert "APIStatusError" in source


def test_nvidia_keys_are_reread_from_environment(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEYS", "key-one,key-two")
    monkeypatch.setenv("NVIDIA_API_KEY", "ignored-single-key")
    assert llm_router._current_api_keys() == ["key-one", "key-two"]


def test_single_key_environment_is_supported(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-real-key")
    assert llm_router._current_api_keys() == ["nvapi-real-key"]


def test_mock_mode_requires_all_configured_keys_to_be_explicit_test_keys(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEYS", "test-one,mock-two")
    assert llm_router._mock_mode() is True
    monkeypatch.setenv("NVIDIA_API_KEYS", "test-one,nvapi-real-key")
    assert llm_router._mock_mode() is False
