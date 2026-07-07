"""Base LLM provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Minimal interface for providers used by WebPilot components."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return a text completion for a prompt."""

