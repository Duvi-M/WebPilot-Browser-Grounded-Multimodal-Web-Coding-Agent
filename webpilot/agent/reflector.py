"""Deterministic reflection over browser evidence and interaction results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from webpilot.browser.executor import ExecutionEvidence
from webpilot.llm.base import LLMProvider, LLMProviderError
from webpilot.llm.mock_provider import MockLLMProvider
from webpilot.task_schema import Task


class Reflector:
    """Classifies known failure modes without calling an LLM."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or MockLLMProvider()

    def reflect(self, evidence: ExecutionEvidence, test_results: list[dict[str, Any]]) -> dict[str, Any]:
        failed = [result for result in test_results if not result.get("passed", False)]
        failure_types: list[str] = []

        if not evidence.npm_install_ok or not evidence.server_started or not evidence.page_loaded:
            failure_types.append("page_load_failure")
        if evidence.console_error_count > 0 or evidence.page_error_count > 0:
            failure_types.append("console_runtime_error")

        failed_names = {result["check_name"] for result in failed}
        if "buttons_exist" in failed_names:
            failure_types.append("missing_button")
        if "form_has_name_email_message" in failed_names:
            failure_types.append("missing_form_field")
        if "submit_shows_feedback" in failed_names:
            failure_types.extend(["submit_button_no_handler", "missing_submit_feedback"])
        if "mobile_has_no_horizontal_overflow" in failed_names:
            failure_types.append("horizontal_overflow_mobile")
        if "nav_menu_opens" in failed_names:
            failure_types.append("nav_menu_no_state_toggle")
        if "tabs_switch_content" in failed_names:
            failure_types.append("tabs_no_state_switch")

        if failed and not failure_types:
            failure_types.append("no_automated_repair_available")

        recommendations = [_recommendation_for(item) for item in dict.fromkeys(failure_types)]
        return {
            "passed": evidence.npm_install_ok
            and evidence.server_started
            and evidence.page_loaded
            and not failed
            and evidence.page_error_count == 0,
            "failed_checks": failed,
            "console_errors_summary": _read_json(evidence.console_logs_path),
            "page_errors_summary": _read_json(evidence.page_errors_path),
            "likely_failure_types": list(dict.fromkeys(failure_types)),
            "repair_recommendations": recommendations,
        }

    def reflect_with_context(
        self,
        task: Task,
        evidence: ExecutionEvidence,
        test_results: list[dict[str, Any]],
        previous_iteration_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        deterministic = self.reflect(evidence, test_results)
        if not _uses_llm(self.llm_provider):
            return deterministic

        prompt = _reflection_prompt(task, evidence, test_results, deterministic, previous_iteration_summary)
        try:
            _set_provider_agent(self.llm_provider, "reflector")
            parsed = _parse_reflection_json(self.llm_provider.complete(prompt))
            _record_provider_validation(self.llm_provider, "passed")
        except (json.JSONDecodeError, ValueError, LLMProviderError) as exc:
            _record_provider_fallback(self.llm_provider, f"LLM reflector fallback: {exc}")
            deterministic["llm_reflection_fallback"] = True
            deterministic["llm_reflection_error"] = str(exc)
            return deterministic

        reflection = dict(deterministic)
        reflection.update(
            {
                "likely_root_cause": parsed["likely_root_cause"],
                "confidence": parsed["confidence"],
                "repair_strategy": parsed["repair_strategy"],
                "files_likely_involved": parsed["files_likely_involved"],
                "short_reasoning": parsed["short_reasoning"],
                "llm_reflection": True,
                "llm_reflection_fallback": False,
            }
        )
        if parsed.get("likely_failure_types"):
            reflection["likely_failure_types"] = parsed["likely_failure_types"]
            reflection["repair_recommendations"] = [parsed["repair_strategy"]]
        return reflection


def _recommendation_for(failure_type: str) -> str:
    recommendations = {
        "missing_form_field": "Add any missing name, email, or message field to the form.",
        "submit_button_no_handler": "Attach a submit handler that prevents default submission and sets feedback state.",
        "missing_submit_feedback": "Render visible confirmation text after form submission.",
        "horizontal_overflow_mobile": "Add CSS rules that prevent horizontal overflow on narrow viewports.",
        "nav_menu_no_state_toggle": "Wire the menu toggle to state and render the nav menu as visible when open.",
        "tabs_no_state_switch": "Wire tab buttons to state and render the active tab panel conditionally.",
        "missing_button": "Add a visible button or CTA.",
        "page_load_failure": "Inspect npm, Vite, and page load errors.",
        "console_runtime_error": "Inspect console/runtime errors before applying a targeted patch.",
        "no_automated_repair_available": "No deterministic repair is available for this failure.",
    }
    return recommendations.get(failure_type, "No deterministic recommendation available.")


def _read_json(path: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _uses_llm(provider: LLMProvider) -> bool:
    return getattr(provider, "provider_name", "mock") != "mock"


def _record_provider_fallback(provider: LLMProvider, reason: str) -> None:
    _record_provider_validation(provider, "failed", reason)
    record = getattr(provider, "record_fallback", None)
    if callable(record):
        record(reason)


def _record_provider_validation(provider: LLMProvider, status: str, error: str | None = None) -> None:
    record = getattr(provider, "record_validation", None)
    if callable(record):
        record(status, error)


def _set_provider_agent(provider: LLMProvider, agent_name: str) -> None:
    setter = getattr(provider, "set_agent_name", None)
    if callable(setter):
        setter(agent_name)


def _reflection_prompt(
    task: Task,
    evidence: ExecutionEvidence,
    test_results: list[dict[str, Any]],
    deterministic_reflection: dict[str, Any],
    previous_iteration_summary: dict[str, Any] | None,
) -> str:
    failed_tests = [result for result in test_results if not result.get("passed", False)]
    return f"""Reflect on this WebPilot browser execution and return strict JSON only.

Required JSON schema:
{{
  "likely_root_cause": "short text",
  "confidence": 0.0,
  "repair_strategy": "short actionable strategy",
  "files_likely_involved": ["relative/path.ext"],
  "short_reasoning": "brief reasoning",
  "likely_failure_types": ["optional known failure type"]
}}

Use confidence from 0.0 to 1.0.
Prefer known failure types when applicable: missing_form_field, submit_button_no_handler,
missing_submit_feedback, horizontal_overflow_mobile, nav_menu_no_state_toggle,
tabs_no_state_switch, missing_button, page_load_failure, console_runtime_error,
no_automated_repair_available.

Task:
{json.dumps(task.to_dict(), indent=2)}

Execution summary:
{json.dumps(_evidence_summary(evidence), indent=2)}

Failed interaction tests:
{json.dumps(failed_tests, indent=2)}

Console errors/logs:
{json.dumps(_read_json(evidence.console_logs_path), indent=2)[:6000]}

Page errors:
{json.dumps(_read_json(evidence.page_errors_path), indent=2)[:4000]}

DOM summary:
{_dom_summary(evidence.dom_snapshot_path)}

Screenshot paths:
{json.dumps({"desktop": str(evidence.desktop_screenshot_path), "mobile": str(evidence.mobile_screenshot_path)}, indent=2)}

Deterministic reflection:
{json.dumps(deterministic_reflection, indent=2)}

Previous iteration summary:
{json.dumps(previous_iteration_summary or {}, indent=2)}
"""


def _evidence_summary(evidence: ExecutionEvidence) -> dict[str, Any]:
    return {
        "npm_install_ok": evidence.npm_install_ok,
        "server_started": evidence.server_started,
        "page_loaded": evidence.page_loaded,
        "fatal_page_error": evidence.fatal_page_error,
        "console_error_count": evidence.console_error_count,
        "page_error_count": evidence.page_error_count,
        "current_url": evidence.current_url,
        "title": evidence.title,
        "dom_snapshot_path": str(evidence.dom_snapshot_path),
    }


def _dom_summary(path: Path) -> str:
    try:
        html = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    text = " ".join(html.replace("<", " <").split())
    return text[:4000]


def _parse_reflection_json(raw: str) -> dict[str, Any]:
    data = json.loads(_strip_json_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("reflection output must be a JSON object")
    root_cause = data.get("likely_root_cause")
    confidence = data.get("confidence")
    strategy = data.get("repair_strategy")
    files = data.get("files_likely_involved", [])
    reasoning = data.get("short_reasoning")
    failure_types = data.get("likely_failure_types", [])
    if not isinstance(root_cause, str) or not root_cause.strip():
        raise ValueError("likely_root_cause must be a non-empty string")
    if not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be numeric")
    if not isinstance(strategy, str) or not strategy.strip():
        raise ValueError("repair_strategy must be a non-empty string")
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        raise ValueError("files_likely_involved must be a list of strings")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("short_reasoning must be a non-empty string")
    if not isinstance(failure_types, list) or not all(isinstance(item, str) for item in failure_types):
        raise ValueError("likely_failure_types must be a list of strings")
    return {
        "likely_root_cause": root_cause,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "repair_strategy": strategy,
        "files_likely_involved": files,
        "short_reasoning": reasoning,
        "likely_failure_types": failure_types,
    }


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text
