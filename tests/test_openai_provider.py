from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from webpilot.agent.coder import Coder
from webpilot.agent.loop import AgentLoop
from webpilot.agent.planner import Planner
from webpilot.evaluation.runner import run_evaluation
from webpilot.llm.base import LLMProvider, LLMProviderError, MissingAPIKeyError
from webpilot.llm.openai_provider import OpenAIProvider, _AuthProviderError, _TransientProviderError
from webpilot.task_schema import Task


def test_openai_provider_successful_call_returns_content() -> None:
    def transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        assert url.endswith("/chat/completions")
        assert payload["model"] == "test-model"
        assert payload["max_tokens"] == 333
        assert payload["temperature"] == 0.1
        assert headers["Authorization"] == "Bearer test-key"
        return {"choices": [{"message": {"content": "hello"}}]}

    provider = OpenAIProvider(api_key="test-key", model="test-model", max_tokens=333, temperature=0.1, transport=transport)

    assert provider.complete("Say hello") == "hello"
    assert provider.usage_summary()["llm_calls_completed"] == 1


def test_openai_provider_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError, match="OPENAI_API_KEY is required"):
        OpenAIProvider()


def test_openai_provider_dry_run_logs_prompt_without_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        raise AssertionError("dry-run must not call the API transport")

    provider = OpenAIProvider(dry_run=True, max_llm_calls=1, transport=transport)
    provider.set_run_context(tmp_path / "llm_calls")
    task = Task.load("webpilot/tasks/sample_text_generation.json")

    plan = Planner(provider).plan(task)

    assert plan.task_type == "text_generation"
    usage = provider.usage_summary()
    assert usage["dry_run_llm"] is True
    assert usage["llm_calls_attempted"] == 1
    assert usage["llm_calls_completed"] == 0
    assert usage["llm_fallback_used"] is True
    artifact_paths = usage["llm_call_artifact_paths"][0]
    assert Path(artifact_paths["prompt"]).exists()
    assert Path(artifact_paths["response"]).read_text(encoding="utf-8").startswith("[DRY RUN]")
    metadata = json.loads(Path(artifact_paths["metadata"]).read_text(encoding="utf-8"))
    assert metadata["status"] == "dry_run"


def test_openai_malformed_plan_json_falls_back_to_deterministic_plan(tmp_path: Path) -> None:
    def transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "{not-json"}}]}

    provider = OpenAIProvider(api_key="test-key", transport=transport, max_retries=0)
    provider.set_run_context(tmp_path / "llm_calls")
    task = Task.load("webpilot/tasks/sample_text_generation.json")

    plan = Planner(provider).plan(task)

    assert {"HeroSection", "PricingSection", "ContactForm"}.issubset({item.name for item in plan.items})
    usage = provider.usage_summary()
    assert usage["llm_calls_attempted"] == 1
    assert usage["llm_calls_completed"] == 1
    assert usage["llm_fallback_used"] is True
    assert usage["llm_errors"]


def test_openai_provider_retries_transient_transport_errors() -> None:
    calls = {"count": 0}

    def transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        calls["count"] += 1
        if calls["count"] < 3:
            raise _TransientProviderError("rate limit")
        return {"choices": [{"message": {"content": "ok after retry"}}]}

    provider = OpenAIProvider(api_key="test-key", transport=transport, max_retries=2)

    assert provider.complete("retry") == "ok after retry"
    assert calls["count"] == 3


def test_openai_provider_does_not_retry_auth_errors() -> None:
    calls = {"count": 0}

    def transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        calls["count"] += 1
        raise _AuthProviderError("bad key")

    provider = OpenAIProvider(api_key="test-key", transport=transport, max_retries=2)

    with pytest.raises(LLMProviderError, match="bad key"):
        provider.complete("auth")
    assert calls["count"] == 1


def test_openai_provider_retries_malformed_http_json(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, body: str) -> None:
            self.body = body

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self.body.encode("utf-8")

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse("{not-json")
        return FakeResponse(json.dumps({"choices": [{"message": {"content": "valid after malformed"}}]}))

    monkeypatch.setattr("webpilot.llm.openai_provider.urlopen", fake_urlopen)
    provider = OpenAIProvider(api_key="test-key", max_retries=1)

    assert provider.complete("json") == "valid after malformed"
    assert calls["count"] == 2


def test_planner_and_coder_accept_openai_shaped_provider(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            json.dumps(
                {
                    "task_type": "text_generation",
                    "items": [
                        {"name": "HeroSection", "kind": "component", "details": {"purpose": "Hero"}},
                        {"name": "ContactForm", "kind": "component", "details": {"purpose": "Contact"}},
                    ],
                    "rationale": "LLM structured plan.",
                }
            ),
            json.dumps(_llm_file_map()),
        ]
    )
    task = Task(
        id="llm_task",
        type="text_generation",
        instruction="Build a landing page with a contact form.",
        repo_path=None,
        expected_behaviors=["Hero section is visible.", "Contact form is visible."],
        test_hints=["Check App.jsx and form fields."],
    )

    plan = Planner(provider).plan(task)
    result = Coder(provider).code(task, plan, tmp_path / "workspace")

    assert plan.items[0].name == "HeroSection"
    assert "src/App.jsx" in result.generated_files
    assert (result.workspace_path / "src" / "App.jsx").read_text(encoding="utf-8").strip()


def test_planner_retries_malformed_llm_plan_json() -> None:
    provider = ScriptedProvider(
        [
            "{not-json",
            json.dumps(
                {
                    "task_type": "text_generation",
                    "items": [{"name": "HeroSection", "kind": "component", "details": {"purpose": "Hero"}}],
                    "rationale": "Recovered on retry.",
                }
            ),
        ]
    )
    task = Task(
        id="retry_task",
        type="text_generation",
        instruction="Build a hero page.",
        repo_path=None,
        expected_behaviors=[],
        test_hints=[],
    )

    plan = Planner(provider).plan(task)

    assert plan.rationale == "Recovered on retry."
    assert provider.responses == []


def test_cli_openai_without_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "webpilot.cli",
            "run",
            "--task",
            "webpilot/tasks/sample_text_generation.json",
            "--llm-provider",
            "openai",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "OPENAI_API_KEY is required" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_flow_accepts_mocked_openai_provider(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from webpilot import cli

    provider = ScriptedProvider(
        [
            json.dumps(
                {
                    "task_type": "text_generation",
                    "items": [
                        {"name": "HeroSection", "kind": "component", "details": {"purpose": "Hero"}},
                        {"name": "PricingSection", "kind": "component", "details": {"purpose": "Pricing"}},
                        {"name": "ContactForm", "kind": "component", "details": {"purpose": "Contact"}},
                    ],
                    "rationale": "Mocked OpenAI plan for CLI flow.",
                }
            ),
            json.dumps(_llm_file_map()),
        ]
    )
    monkeypatch.setattr(cli, "_create_llm_provider", lambda name, **kwargs: provider)

    cli.run_task(
        Path("webpilot/tasks/sample_text_generation.json"),
        variant="base",
        max_iterations=1,
        llm_provider_name="openai",
    )

    output = capsys.readouterr().out
    assert "Generated workspace:" in output
    assert "Summary:" in output


def test_agent_summary_includes_mock_llm_metadata() -> None:
    task = Task(
        id="summary_task",
        type="text_generation",
        instruction="Build a hero.",
        repo_path=None,
        expected_behaviors=[],
        test_hints=[],
    )

    summary = AgentLoop(variant="base", max_iterations=1).run(task).summary

    assert summary["llm_provider"] == "mock"
    assert summary["dry_run_llm"] is False
    assert summary["llm_calls_attempted"] == 0
    assert summary["llm_calls_completed"] == 0
    assert summary["llm_call_artifact_paths"] == []
    assert summary["llm_fallback_used"] is False
    assert summary["llm_errors"] == []


def test_evaluation_runner_blocks_openai_batch_without_allow_flag() -> None:
    with pytest.raises(ValueError, match="OpenAI evaluation batch requires --allow-paid-batch"):
        run_evaluation(Path("webpilot/tasks"), "browser-feedback", 1, llm_provider_name="openai")


class ScriptedProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    def complete(self, prompt: str) -> str:
        assert prompt
        return self.responses.pop(0)


def _llm_file_map() -> dict[str, str]:
    return {
        "package.json": '{"scripts":{"dev":"vite"},"dependencies":{"@vitejs/plugin-react":"^4.3.4","vite":"^6.0.7","react":"^18.3.1","react-dom":"^18.3.1"}}\n',
        "vite.config.js": "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({ plugins: [react()] });\n",
        "index.html": '<div id="root"></div><script type="module" src="/src/main.jsx"></script>\n',
        "src/main.jsx": "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App.jsx';\nReactDOM.createRoot(document.getElementById('root')).render(<App />);\n",
        "src/App.jsx": "export default function App() { return <main><h1>Hello</h1><form><input name=\"name\" /></form></main>; }\n",
        "src/App.css": "body { margin: 0; }\n",
    }
