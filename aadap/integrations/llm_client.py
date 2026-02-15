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
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


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
