import inspect

from core import llm_router


def test_model_failover_list_has_multiple_current_candidates():
    assert len(llm_router.FALLBACK_MODELS) >= 3
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


def test_openrouter_key_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert llm_router._openrouter_key() == "sk-or-test"


def test_openrouter_free_router_is_configured():
    assert llm_router.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
    assert llm_router.OPENROUTER_FREE_MODEL == "openrouter/free"
    source = inspect.getsource(llm_router.LLMRouter._generate)
    assert "_try_openrouter" in source
    assert "_generate_nvidia" in source


def test_mock_mode_requires_all_configured_test_keys(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEYS", "test-one,mock-two")
    assert llm_router._mock_mode() is True
    monkeypatch.setenv("NVIDIA_API_KEYS", "test-one,nvapi-real-key")
    assert llm_router._mock_mode() is False
