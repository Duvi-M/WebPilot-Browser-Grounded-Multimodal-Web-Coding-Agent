"""Deterministic mock provider for local development and tests."""

from __future__ import annotations

from webpilot.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """A no-network provider that returns deterministic text."""

    def complete(self, prompt: str) -> str:
        normalized = " ".join(prompt.strip().split())
        return f"mock-response:{normalized[:120]}"

