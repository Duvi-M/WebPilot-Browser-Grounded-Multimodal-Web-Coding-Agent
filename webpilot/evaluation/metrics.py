"""Simple MVP evaluation metrics."""

from __future__ import annotations

from typing import Any

from webpilot.browser.executor import ExecutionEvidence


def executability(evidence: ExecutionEvidence | None) -> bool:
    if evidence is None:
        return False
    return evidence.npm_install_ok and evidence.server_started and evidence.page_loaded and not evidence.fatal_page_error


def interaction_correctness(test_results: list[dict[str, Any]]) -> float:
    if not test_results:
        return 0.0
    passed = sum(1 for result in test_results if result.get("passed") is True)
    return passed / len(test_results)


def patch_quality() -> None:
    """Future work: score repair localization and regression risk for editing/repair tasks."""
    return None


def visual_quality() -> None:
    """Future work: score screenshots with a multimodal judge or visual comparison rubric."""
    return None

