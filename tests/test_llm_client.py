"""
AADAP — LLM Client Tests
==========================
Tests for the LLM client abstraction and implementations.
"""

from __future__ import annotations

import pytest

from aadap.integrations.llm_client import (
    BaseLLMClient,
    LLMResponse,
    MockLLMClient,
    AzureOpenAIClient,
)


# ── MockLLMClient Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_client_returns_configured_response():
    """MockLLMClient returns the configured default response."""
    client = MockLLMClient(default_response="Hello, world!")
    response = await client.complete("Say hello")
    assert response.content == "Hello, world!"
    assert isinstance(response, LLMResponse)


@pytest.mark.asyncio
async def test_mock_client_returns_configured_tokens():
    """MockLLMClient returns the configured token count."""
    client = MockLLMClient(tokens_per_response=500)
    response = await client.complete("test")
    assert response.tokens_used == 500


@pytest.mark.asyncio
async def test_mock_client_uses_provided_model():
    """MockLLMClient uses the provided model name."""
    client = MockLLMClient(default_model="mock-model")
    response = await client.complete("test", model="custom-model")
    assert response.model == "custom-model"


@pytest.mark.asyncio
async def test_mock_client_counts_tokens():
    """MockLLMClient estimates tokens using word-based heuristic."""
    client = MockLLMClient()
    tokens = await client.count_tokens("hello world test")
    assert tokens >= 1


@pytest.mark.asyncio
async def test_mock_client_metadata_includes_prompt_length():
    """MockLLMClient includes prompt length in metadata."""
    client = MockLLMClient()
    response = await client.complete("test prompt")
    assert "prompt_length" in response.metadata
    assert response.metadata["prompt_length"] == len("test prompt")


# ── AzureOpenAIClient Tests ───────────────────────────────────────────────

def test_azure_openai_client_from_settings_missing_key():
    """AzureOpenAIClient.from_settings raises when API key is missing."""
    import os
    original = os.environ.get("AADAP_AZURE_OPENAI_API_KEY")
    if "AADAP_AZURE_OPENAI_API_KEY" in os.environ:
        del os.environ["AADAP_AZURE_OPENAI_API_KEY"]

    from aadap.core.config import get_settings
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError, match="AADAP_AZURE_OPENAI_API_KEY"):
            AzureOpenAIClient.from_settings()
    finally:
        if original:
            os.environ["AADAP_AZURE_OPENAI_API_KEY"] = original
        get_settings.cache_clear()


def test_azure_openai_client_init():
    """AzureOpenAIClient can be initialized directly."""
    client = AzureOpenAIClient(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        api_version="2024-02-01",
        deployment_name="gpt-4o",
    )
    assert client._api_key == "test-key"
    assert client._endpoint == "https://test.openai.azure.com/"
    assert client._deployment_name == "gpt-4o"


def test_azure_openai_client_lazy_client_init():
    """AzureOpenAClient lazily initializes the OpenAI client."""
    client = AzureOpenAIClient(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        api_version="2024-02-01",
        deployment_name="gpt-4o",
    )
    assert client._client is None


# ── Abstract Interface Tests ──────────────────────────────────────────────

def test_base_llm_client_is_abstract():
    """BaseLLMClient cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseLLMClient()
