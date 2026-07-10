"""Deterministic reflection over browser evidence and interaction results."""

from __future__ import annotations

import json
from typing import Any

from webpilot.browser.executor import ExecutionEvidence


class Reflector:
    """Classifies known failure modes without calling an LLM."""

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


def _recommendation_for(failure_type: str) -> str:
    recommendations = {
        "missing_form_field": "Add any missing name, email, or message field to the form.",
        "submit_button_no_handler": "Attach a submit handler that prevents default submission and sets feedback state.",
        "missing_submit_feedback": "Render visible confirmation text after form submission.",
        "horizontal_overflow_mobile": "Add CSS rules that prevent horizontal overflow on narrow viewports.",
        "nav_menu_no_state_toggle": "Wire the menu toggle to state and render the nav menu as visible when open.",
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
