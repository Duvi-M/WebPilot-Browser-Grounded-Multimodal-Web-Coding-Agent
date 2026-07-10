from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from webpilot.config import chromium_launch_args


def test_cli_base_smoke_runs_browser_grounded_generation() -> None:
    _require_browser_stack()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "webpilot.cli",
            "run",
            "--task",
            "webpilot/tasks/sample_text_generation.json",
            "--variant",
            "base",
            "--max-iterations",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary_line = next(line for line in result.stdout.splitlines() if line.startswith("Summary: "))
    summary_path = Path(summary_line.removeprefix("Summary: "))
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "final_status" in summary or "status" in summary
    assert summary.get("executability_status")
    assert summary.get("interaction_correctness_status") or summary.get("interaction_correctness_score") is not None


def test_cli_invalid_task_error_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "webpilot.cli", "run", "--task", "missing-task.json"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert result.stderr.startswith("Error:")
    assert "Traceback" not in result.stderr


def _require_browser_stack() -> None:
    if shutil.which("npm") is None:
        pytest.skip("npm is not installed; skipping browser-grounded CLI smoke test.")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        pytest.skip(f"Playwright Python package is unavailable: {exc}")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=chromium_launch_args())
            browser.close()
    except Exception as exc:
        pytest.skip(f"Playwright Chromium browser is unavailable: {exc}")
