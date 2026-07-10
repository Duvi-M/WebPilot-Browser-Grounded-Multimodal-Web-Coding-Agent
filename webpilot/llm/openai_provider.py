"""OpenAI chat completions provider for WebPilot."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from webpilot.config import DEFAULT_OPENAI_MODEL
from webpilot.llm.base import LLMProvider, LLMProviderError, MissingAPIKeyError


Transport = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


class OpenAIProvider(LLMProvider):
    """Small stdlib-based OpenAI provider with injectable transport for tests."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise MissingAPIKeyError("OPENAI_API_KEY is required when --llm-provider openai is used")
        self.model = model or os.environ.get("WEBPILOT_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.transport = transport or _default_transport

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a precise coding-agent component. Return only the requested content."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.transport("https://api.openai.com/v1/chat/completions", payload, headers, self.timeout_seconds)
                return _extract_message_content(response)
            except MissingAPIKeyError:
                raise
            except _AuthProviderError as exc:
                raise LLMProviderError(str(exc)) from exc
            except _TransientProviderError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.5 * (attempt + 1))
            except LLMProviderError:
                raise
            except Exception as exc:
                raise LLMProviderError(f"OpenAI provider failed: {exc}") from exc

        raise LLMProviderError(f"OpenAI provider failed after retries: {last_error}") from last_error


class _TransientProviderError(LLMProviderError):
    pass


class _AuthProviderError(LLMProviderError):
    pass


def _default_transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise _AuthProviderError("OpenAI authentication failed; check OPENAI_API_KEY") from exc
        if exc.code in {408, 409, 429, 500, 502, 503, 504}:
            raise _TransientProviderError(f"Transient OpenAI HTTP error: {exc.code}") from exc
        raise LLMProviderError(f"OpenAI HTTP error: {exc.code}") from exc
    except TimeoutError as exc:
        raise _TransientProviderError("OpenAI request timed out") from exc
    except URLError as exc:
        raise _TransientProviderError(f"OpenAI network error: {exc.reason}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _TransientProviderError("OpenAI response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMProviderError("OpenAI response was not a JSON object")
    return parsed


def _extract_message_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError("OpenAI response did not contain choices[0].message.content") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMProviderError("OpenAI response content was empty")
    return content
