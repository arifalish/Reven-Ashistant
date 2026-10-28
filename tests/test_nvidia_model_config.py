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


def test_cloudflare_workers_ai_config_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
    assert llm_router.LLMRouter()._cloudflare_credentials() == ("account-123", "cf-token")


def test_cloudflare_workers_ai_uses_openai_compatible_endpoint():
    assert llm_router.CLOUDFLARE_DEFAULT_MODEL == "@cf/zai-org/glm-4.7-flash"
    source = inspect.getsource(llm_router.LLMRouter._try_cloudflare)
    assert "/ai/v1" in source
    assert "CLOUDFLARE_API_TOKEN" in source


def test_provider_chain_includes_cloudflare_before_nvidia():
    source = inspect.getsource(llm_router.LLMRouter._generate)
    assert source.index("_try_openrouter") < source.index("_try_cloudflare") < source.index("_generate_nvidia")


def test_nvidia_fallback_prioritizes_healthy_model_then_kimi_deepseek_glm_and_qwen():
    models = llm_router.FALLBACK_MODELS
    assert models[0] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert models.index("moonshotai/kimi-k3") < models.index("deepseek-ai/deepseek-v4-flash")
    assert "z-ai/glm-5.3-flash" in models
    assert "qwen/qwen3-next-80b-a3b-instruct" in models


def test_rate_limited_models_get_cooldown():
    assert llm_router.MODEL_COOLDOWN_SECONDS[429] > 0
    assert llm_router.MODEL_COOLDOWN_SECONDS[402] > llm_router.MODEL_COOLDOWN_SECONDS[429]


def test_non_chat_models_are_filtered_from_discovery():
    assert "embed" in llm_router.NON_CHAT_MODEL_MARKERS
    assert "safety" in llm_router.NON_CHAT_MODEL_MARKERS


async def test_sticky_model_memory_remembers_last_success(monkeypatch):
    monkeypatch.setattr(llm_router, "redis_client", None)
    instance = llm_router.LLMRouter()
    await instance._remember_preferred_model("provider:key-fingerprint", "nvidia/healthy-model")
    assert await instance._get_preferred_model("provider:key-fingerprint") == "nvidia/healthy-model"
