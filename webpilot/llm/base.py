"""Base LLM provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot complete a request."""


class MissingAPIKeyError(LLMProviderError):
    """Raised when a provider needs an API key that is not configured."""


class LLMProvider(ABC):
    """Minimal interface for providers used by WebPilot components."""

    provider_name = "base"

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return a text completion for a prompt."""
