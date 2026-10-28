from core.llm_router import router


def test_all_tiers_use_active_nvidia_model():
    expected = "deepseek-ai/deepseek-v4-flash"
    assert expected in router.primary_client.base_url or router.primary_client.base_url.endswith("/v1")
    import inspect
    from core import llm_router
    source = inspect.getsource(llm_router.LLMRouter)
    assert '"meta/llama-3.3-70b-instruct"' not in source
    assert '"meta/llama-3.1-70b-instruct"' not in source
    assert '"qwen/qwen2.5-coder-32b-instruct"' not in source
    assert source.count(expected) >= 4
