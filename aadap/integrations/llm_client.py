"""
AADAP — LLM Client Abstraction
==================================
Thin abstraction layer for LLM interactions.

Architecture layer: L3 (Integration).

Phase 3 scope: abstract interface + mock implementation only.
No real API calls — no domain-specific logic (PHASE_3_CONTRACTS §Non-Goals).

Usage:
    client = MockLLMClient(default_response="Hello")
    response = await client.complete("Say hello")
    print(response.content)  # "Hello"

    # Real client:
    client = AzureOpenAIClient.from_settings()
    response = await client.complete("Say hello")
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from aadap.core.config import get_settings
from aadap.core.logging import get_logger

logger = get_logger(__name__)


# ── Response Model ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class LLMResponse:
    """Response from an LLM completion call."""

    content: str
    tokens_used: int
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Abstract Base ───────────────────────────────────────────────────────


class BaseLLMClient(abc.ABC):
    """
    Abstract LLM client.

    Concrete implementations (e.g. Azure OpenAI, Anthropic) will be
    added in later phases.  Phase 3 provides the interface contract
    and a ``MockLLMClient`` for testing.
    """

    @abc.abstractmethod
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Send a completion request to the LLM.

        Parameters
        ----------
        prompt
            The input text prompt.
        model
            Model identifier (e.g. ``gpt-4o``).  None uses the default.
        max_tokens
            Maximum tokens in the response.

        Returns
        -------
        LLMResponse
        """
        ...

    @abc.abstractmethod
    async def count_tokens(self, text: str) -> int:
        """
        Estimate token count for the given text.

        Parameters
        ----------
        text
            Input text to tokenize.

        Returns
        -------
        int
            Estimated token count.
        """
        ...


# ── Mock Implementation ────────────────────────────────────────────────


class MockLLMClient(BaseLLMClient):
    """
    Mock LLM client for testing.

    Returns configurable canned responses.  Token counting uses a
    simple word-based heuristic (≈ 1.3 tokens per word).
    """

    def __init__(
        self,
        default_response: str = "Mock LLM response",
        default_model: str = "mock-model",
        tokens_per_response: int = 100,
    ) -> None:
        self._default_response = default_response
        self._default_model = default_model
        self._tokens_per_response = tokens_per_response

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Return the configured canned response."""
        return LLMResponse(
            content=self._default_response,
            tokens_used=self._tokens_per_response,
            model=model or self._default_model,
            metadata={"prompt_length": len(prompt)},
        )

    async def count_tokens(self, text: str) -> int:
        """Estimate tokens using simple word-based heuristic."""
        word_count = len(text.split())
        return max(1, int(word_count * 1.3))


# ── Azure OpenAI Implementation ─────────────────────────────────────────


class AzureOpenAIClient(BaseLLMClient):
    """
    Real Azure OpenAI client for production use.

    Uses the OpenAI SDK with Azure AI Foundry credentials.
    Requires the following environment variables:
        - AADAP_AZURE_OPENAI_API_KEY
        - CAAAP_AZURE_OPENAI_ENDPOINT
        - CAAAP_AZURE_OPENAI_DEPLOYMENT_NAME
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        api_version: str,
        deployment_name: str,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._api_version = api_version
        self._deployment_name = deployment_name
        self._client = None
        self._encoding = None

    @classmethod
    def from_settings(cls) -> "AzureOpenAIClient":
        """Create an AzureOpenAIClient from application settings."""
        settings = get_settings()
        if not settings.azure_openai_api_key:
            raise ValueError(
                "AADAP_AZURE_OPENAI_API_KEY is required for AzureOpenAIClient"
            )
        if not settings.azure_openai_endpoint:
            raise ValueError(
                "AADAP_AZURE_OPENAI_ENDPOINT is required for AzureOpenAIClient"
            )
        if not settings.azure_openai_deployment_name:
            raise ValueError(
                "AADAP_AZURE_OPENAI_DEPLOYMENT_NAME is required for AzureOpenAIClient"
            )
        return cls(
            api_key=settings.azure_openai_api_key.get_secret_value(),
            endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            deployment_name=settings.azure_openai_deployment_name,
        )

    def _get_client(self):
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            from openai import AsyncAzureOpenAI
            self._client = AsyncAzureOpenAI(
                api_key=self._api_key,
                azure_endpoint=self._endpoint,
                api_version=self._api_version,
            )
        return self._client

    def _get_encoding(self):
        """Lazily initialize the tiktoken encoding."""
        if self._encoding is None:
            import tiktoken
            self._encoding = tiktoken.encoding_for_model("gpt-4")
        return self._encoding

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a completion request to Azure OpenAI."""
        client = self._get_client()
        deployment = model or self._deployment_name

        logger.debug(
            "llm.complete.start",
            deployment=deployment,
            prompt_length=len(prompt),
            max_tokens=max_tokens,
        )

        try:
            response = await client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0

            logger.debug(
                "llm.complete.success",
                deployment=deployment,
                tokens_used=tokens_used,
                response_length=len(content),
            )

            return LLMResponse(
                content=content,
                tokens_used=tokens_used,
                model=deployment,
                metadata={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "finish_reason": response.choices[0].finish_reason if response.choices else None,
                },
            )
        except Exception as exc:
            logger.error(
                "llm.complete.error",
                deployment=deployment,
                error=str(exc),
            )
            raise

    async def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        encoding = self._get_encoding()
        return len(encoding.encode(text))
