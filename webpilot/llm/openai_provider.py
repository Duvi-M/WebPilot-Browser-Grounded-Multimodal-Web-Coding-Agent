"""OpenAI chat completions provider for WebPilot."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from webpilot.config import DEFAULT_OPENAI_MAX_TOKENS, DEFAULT_OPENAI_MODEL, DEFAULT_OPENAI_TEMPERATURE
from webpilot.llm.base import LLMProvider, LLMProviderError, MissingAPIKeyError


Transport = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


class OpenAIProvider(LLMProvider):
    """Small stdlib-based OpenAI provider with injectable transport for tests."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        dry_run: bool = False,
        max_llm_calls: int | None = 1,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.dry_run = dry_run
        if not self.api_key and not self.dry_run:
            raise MissingAPIKeyError("OPENAI_API_KEY is required when --llm-provider openai is used")
        self.model = model or os.environ.get("WEBPILOT_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.max_tokens = max_tokens if max_tokens is not None else _env_int("WEBPILOT_OPENAI_MAX_TOKENS", DEFAULT_OPENAI_MAX_TOKENS)
        self.temperature = (
            temperature
            if temperature is not None
            else _env_float("WEBPILOT_OPENAI_TEMPERATURE", DEFAULT_OPENAI_TEMPERATURE)
        )
        self.max_llm_calls = max_llm_calls
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.transport = transport or _default_transport
        self.calls_attempted = 0
        self.calls_completed = 0
        self.errors: list[str] = []
        self.call_artifact_paths: list[dict[str, str]] = []
        self.fallback_used = False
        self._llm_calls_dir: Path | None = None

    def set_run_context(self, llm_calls_dir: Path) -> None:
        self._llm_calls_dir = llm_calls_dir

    def record_fallback(self, reason: str) -> None:
        self.fallback_used = True
        if reason and reason not in self.errors:
            self.errors.append(reason)

    def usage_summary(self) -> dict[str, Any]:
        return {
            "llm_provider": self.provider_name,
            "openai_model": self.model,
            "dry_run_llm": self.dry_run,
            "max_llm_calls": self.max_llm_calls,
            "llm_calls_attempted": self.calls_attempted,
            "llm_calls_completed": self.calls_completed,
            "llm_call_artifact_paths": self.call_artifact_paths,
            "llm_fallback_used": self.fallback_used,
            "llm_errors": self.errors,
        }

    def complete(self, prompt: str) -> str:
        system_message = "You are a precise coding-agent component. Return only the requested content."
        if self.max_llm_calls is not None and self.calls_completed >= self.max_llm_calls:
            self.calls_attempted += 1
            message = f"OpenAI call budget exhausted: max_llm_calls={self.max_llm_calls}"
            self.errors.append(message)
            raise LLMProviderError(message)

        self.calls_attempted += 1
        call_index = self.calls_attempted
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        prompt_path, response_path, metadata_path = self._write_call_start(call_index, prompt, system_message)

        if self.dry_run:
            response_text = "[DRY RUN] OpenAI API call skipped. Prompt was logged for inspection."
            metadata = self._metadata(call_index, status="dry_run", prompt_path=prompt_path, response_path=response_path)
            self._write_call_end(response_path, metadata_path, response_text, metadata)
            message = "OpenAI dry-run recorded prompt; no API call was made"
            self.errors.append(message)
            raise LLMProviderError(message)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.transport("https://api.openai.com/v1/chat/completions", payload, headers, self.timeout_seconds)
                content = _extract_message_content(response)
                self.calls_completed += 1
                metadata = self._metadata(
                    call_index,
                    status="completed",
                    prompt_path=prompt_path,
                    response_path=response_path,
                    provider_metadata=_provider_metadata(response),
                )
                self._write_call_end(response_path, metadata_path, content, metadata)
                return content
            except MissingAPIKeyError:
                raise
            except _AuthProviderError as exc:
                self.errors.append(str(exc))
                self._write_call_end(response_path, metadata_path, "", self._metadata(call_index, "failed", prompt_path, response_path, error=str(exc)))
                raise LLMProviderError(str(exc)) from exc
            except _TransientProviderError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.5 * (attempt + 1))
            except LLMProviderError as exc:
                self.errors.append(str(exc))
                self._write_call_end(response_path, metadata_path, "", self._metadata(call_index, "failed", prompt_path, response_path, error=str(exc)))
                raise
            except Exception as exc:
                self.errors.append(f"OpenAI provider failed: {exc}")
                self._write_call_end(response_path, metadata_path, "", self._metadata(call_index, "failed", prompt_path, response_path, error=str(exc)))
                raise LLMProviderError(f"OpenAI provider failed: {exc}") from exc

        message = f"OpenAI provider failed after retries: {last_error}"
        self.errors.append(message)
        self._write_call_end(response_path, metadata_path, "", self._metadata(call_index, "failed", prompt_path, response_path, error=message))
        raise LLMProviderError(message) from last_error

    def _write_call_start(self, call_index: int, prompt: str, system_message: str) -> tuple[Path | None, Path | None, Path | None]:
        if self._llm_calls_dir is None:
            return None, None, None
        self._llm_calls_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"llm_call_{call_index:03d}"
        prompt_path = self._llm_calls_dir / f"{prefix}_prompt.txt"
        response_path = self._llm_calls_dir / f"{prefix}_response.txt"
        metadata_path = self._llm_calls_dir / f"{prefix}_metadata.json"
        prompt_path.write_text(f"System:\n{system_message}\n\nUser:\n{prompt}", encoding="utf-8")
        metadata = self._metadata(call_index, status="started", prompt_path=prompt_path, response_path=response_path)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.call_artifact_paths.append(
            {
                "prompt": str(prompt_path),
                "response": str(response_path),
                "metadata": str(metadata_path),
            }
        )
        return prompt_path, response_path, metadata_path

    def _write_call_end(
        self,
        response_path: Path | None,
        metadata_path: Path | None,
        response_text: str,
        metadata: dict[str, Any],
    ) -> None:
        if response_path is not None:
            response_path.write_text(response_text.rstrip() + "\n", encoding="utf-8")
        if metadata_path is not None:
            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _metadata(
        self,
        call_index: int,
        status: str,
        prompt_path: Path | None,
        response_path: Path | None,
        error: str | None = None,
        provider_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "call_index": call_index,
            "provider": self.provider_name,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "dry_run": self.dry_run,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_path": str(prompt_path) if prompt_path is not None else None,
            "response_path": str(response_path) if response_path is not None else None,
        }
        if provider_metadata is not None:
            metadata["provider_metadata"] = provider_metadata
        if error is not None:
            metadata["error"] = error
        return metadata


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


def _provider_metadata(response: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("id", "model", "created", "usage", "system_fingerprint"):
        if key in response:
            metadata[key] = response[key]
    return metadata


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise LLMProviderError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise LLMProviderError(f"{name} must be greater than 0")
    return parsed


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise LLMProviderError(f"{name} must be a number") from exc
    if parsed < 0:
        raise LLMProviderError(f"{name} must be non-negative")
    return parsed
