from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from webpilot.agent.coder import Coder
from webpilot.agent.planner import Planner
from webpilot.agent.reflector import Reflector
from webpilot.agent.repairer import Repairer
from webpilot.browser.executor import ExecutionEvidence
from webpilot.llm.base import LLMProvider
from webpilot.llm.openai_provider import OpenAIProvider
from webpilot.task_schema import Task


def test_llm_coder_generates_complete_vite_workspace(tmp_path: Path) -> None:
    provider = ScriptedProvider([json.dumps(_vite_file_map("<h1>LLM generated</h1>"))])
    task = Task.load("webpilot/tasks/sample_text_generation.json")
    plan = Planner().plan(task)

    result = Coder(provider).code(task, plan, tmp_path / "workspace")

    assert (result.workspace_path / "src" / "App.jsx").read_text(encoding="utf-8").count("LLM generated") == 1
    assert result.message == "Generated a Vite + React workspace with LLM provider."


def test_llm_coder_edits_existing_workspace(tmp_path: Path) -> None:
    task = Task.load("webpilot/tasks/sample_editing_secondary_cta.json")
    plan = Planner().plan(task)
    edited_app = Path("webpilot/examples/editable_landing_app/src/App.jsx").read_text(encoding="utf-8").replace(
        '<a className="cta-button" href="#contact">Talk to us</a>',
        '<a className="cta-button" href="#contact">Talk to us</a>\n        <a className="secondary-cta-button" href="#pricing">View case studies</a>',
    )
    provider = ScriptedProvider([json.dumps({"src/App.jsx": edited_app})])

    result = Coder(provider).code(task, plan, tmp_path / "workspace")

    assert "View case studies" in (result.workspace_path / "src" / "App.jsx").read_text(encoding="utf-8")
    assert result.change_records is not None
    assert result.change_records[0]["llm_edit"] is True


def test_llm_coder_invalid_json_falls_back_to_deterministic(tmp_path: Path) -> None:
    def transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "{not-json"}}]}

    provider = OpenAIProvider(api_key="test-key", transport=transport, max_retries=0)
    provider.set_run_context(tmp_path / "llm_calls")
    task = Task.load("webpilot/tasks/sample_text_generation.json")
    plan = Planner().plan(task)

    result = Coder(provider).code(task, plan, tmp_path / "workspace")

    assert (result.workspace_path / "src" / "components" / "ContactForm.jsx").exists()
    assert provider.usage_summary()["llm_fallback_used"] is True


def test_llm_reflector_returns_structured_context(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            json.dumps(
                {
                    "likely_root_cause": "The form never renders submit feedback.",
                    "confidence": 0.82,
                    "repair_strategy": "Add submit state and visible status text.",
                    "files_likely_involved": ["src/App.jsx"],
                    "short_reasoning": "The submit interaction failed and no status text appeared.",
                    "likely_failure_types": ["submit_button_no_handler"],
                }
            )
        ]
    )
    evidence = _evidence(tmp_path)
    task = Task.load("webpilot/tasks/sample_diagnostic_repair.json")

    reflection = Reflector(provider).reflect_with_context(
        task,
        evidence,
        [{"check_name": "submit_shows_feedback", "passed": False, "details": "No feedback."}],
    )

    assert reflection["llm_reflection"] is True
    assert reflection["likely_root_cause"].startswith("The form")
    assert reflection["likely_failure_types"] == ["submit_button_no_handler"]


def test_llm_repair_applies_safe_full_file_replacement(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "App.jsx").write_text("export default function App() { return <p>Broken</p>; }\n", encoding="utf-8")
    repaired = "export default function App() { return <p>Fixed</p>; }\n"
    provider = ScriptedProvider([json.dumps({"files": [{"path": "src/App.jsx", "content": repaired}]})])
    task = Task.load("webpilot/tasks/sample_diagnostic_repair.json")

    result = Repairer(provider).repair({"likely_failure_types": ["no_automated_repair_available"]}, workspace, task=task)

    assert result["repairs_applied"] == ["llm_repair"]
    assert (workspace / "src" / "App.jsx").read_text(encoding="utf-8") == repaired
    assert result["diffs"]


class ScriptedProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    def complete(self, prompt: str) -> str:
        assert prompt
        return self.responses.pop(0)


def _vite_file_map(app: str) -> dict[str, str]:
    return {
        "package.json": '{"scripts":{"dev":"vite"},"dependencies":{"@vitejs/plugin-react":"^4.3.4","vite":"^6.0.7","react":"^18.3.1","react-dom":"^18.3.1"}}\n',
        "vite.config.js": "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({ plugins: [react()] });\n",
        "index.html": '<div id="root"></div><script type="module" src="/src/main.jsx"></script>\n',
        "src/main.jsx": "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App.jsx';\nReactDOM.createRoot(document.getElementById('root')).render(<App />);\n",
        "src/App.jsx": f"export default function App() {{ return <main>{app}</main>; }}\n",
        "src/App.css": "body { margin: 0; }\n",
    }


def _evidence(tmp_path: Path) -> ExecutionEvidence:
    console = tmp_path / "console_logs.json"
    errors = tmp_path / "page_errors.json"
    dom = tmp_path / "dom_snapshot.html"
    console.write_text("[]\n", encoding="utf-8")
    errors.write_text("[]\n", encoding="utf-8")
    dom.write_text("<html><body><form><button>Send</button></form></body></html>", encoding="utf-8")
    screenshot = tmp_path / "screenshot.png"
    screenshot.write_text("", encoding="utf-8")
    log = tmp_path / "server.log"
    log.write_text("", encoding="utf-8")
    return ExecutionEvidence(
        workspace_path=tmp_path,
        app_url="http://127.0.0.1:1",
        npm_install_ok=True,
        server_started=True,
        page_loaded=True,
        fatal_page_error=False,
        console_error_count=0,
        page_error_count=0,
        desktop_screenshot_path=screenshot,
        mobile_screenshot_path=screenshot,
        dom_snapshot_path=dom,
        console_logs_path=console,
        page_errors_path=errors,
        dev_server_stdout_path=log,
        dev_server_stderr_path=log,
        current_url="http://127.0.0.1:1",
        title="Test",
    )
