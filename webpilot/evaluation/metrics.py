"""Simple MVP evaluation metrics."""

from __future__ import annotations

from pathlib import Path
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


def patch_quality(
    task_type: str,
    workspace_path: Path,
    generated_files: list[str],
    repairs_attempted: list[dict[str, Any]],
) -> float | None:
    """Heuristic patch score for repair/editing tasks.

    Formula: 40% localization, 30% size, 30% targetedness.
    Localization rewards touching a small fraction of workspace files.
    Size rewards small unified diffs; missing diffs fall back to touched-file count as a defensive proxy.
    Targetedness rewards applied repairs or deterministic edits and penalizes no-op repair attempts.
    This is a proxy for patch quality, not an LLM or human judgment.
    """
    if task_type == "text_generation":
        return None

    total_files = max(1, _workspace_file_count(workspace_path))
    modified_files = _modified_files(task_type, generated_files, repairs_attempted)
    modified_count = max(1, len(modified_files))
    localization_score = max(0.0, 1.0 - (modified_count / total_files))

    changed_lines = _changed_diff_lines(repairs_attempted)
    if changed_lines:
        size_score = max(0.0, 1.0 - (changed_lines / 120.0))
    else:
        size_score = max(0.0, 1.0 - (modified_count / 8.0))

    if task_type == "editing":
        targeted_score = 1.0 if modified_files else 0.0
    else:
        targeted_score = 1.0 if any(repair.get("repairs_applied") for repair in repairs_attempted) else 0.0

    score = (0.4 * localization_score) + (0.3 * size_score) + (0.3 * targeted_score)
    return round(max(0.0, min(1.0, score)), 4)


def visual_quality() -> None:
    """Future work: score screenshots with a multimodal judge or visual comparison rubric."""
    return None


def _workspace_file_count(workspace_path: Path) -> int:
    ignored_parts = {"node_modules", "dist", "build", ".git"}
    return sum(
        1
        for path in workspace_path.rglob("*")
        if path.is_file() and not ignored_parts.intersection(path.relative_to(workspace_path).parts)
    )


def _modified_files(task_type: str, generated_files: list[str], repairs_attempted: list[dict[str, Any]]) -> list[str]:
    files: list[str] = []
    for repair in repairs_attempted:
        for path in repair.get("files_modified", []):
            if isinstance(path, str) and path not in files:
                files.append(path)
    if files:
        return files
    if task_type == "editing":
        edit_markers = (
            "src/App.jsx",
            "src/App.css",
            "src/components/TestimonialsSection.jsx",
            "src/components/FAQSection.jsx",
            "src/components/NewsletterSignup.jsx",
        )
        return [path for path in generated_files if path in edit_markers]
    return []


def _changed_diff_lines(repairs_attempted: list[dict[str, Any]]) -> int:
    changed = 0
    for repair in repairs_attempted:
        diffs = repair.get("diffs", {})
        if not isinstance(diffs, dict):
            continue
        for diff in diffs.values():
            if not isinstance(diff, str):
                continue
            for line in diff.splitlines():
                if (line.startswith("+") and not line.startswith("+++")) or (
                    line.startswith("-") and not line.startswith("---")
                ):
                    changed += 1
    return changed
