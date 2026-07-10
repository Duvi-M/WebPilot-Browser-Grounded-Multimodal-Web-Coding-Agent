from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from webpilot.agent.coder import Coder
from webpilot.agent.planner import Planner
from webpilot.task_schema import Task


def test_editing_task_requires_repo_path() -> None:
    with pytest.raises(ValueError, match="editing tasks require"):
        Task.from_dict(
            {
                "id": "task_edit_missing_repo",
                "type": "editing",
                "instruction": "Add a testimonials section.",
                "repo_path": None,
                "expected_behaviors": [],
                "test_hints": [],
            }
        )


def test_editing_task_loads_with_repo_path() -> None:
    task = _sample_editing_task()

    assert task.type == "editing"
    assert task.repo_path == "webpilot/examples/editable_landing_app"


def test_editing_planner_targets_testimonials_files() -> None:
    plan = Planner().plan(_sample_editing_task())

    assert plan.task_type == "editing"
    testimonials_item = next(item for item in plan.items if item.name == "TestimonialsSection")
    assert testimonials_item.kind == "edit_target"
    assert testimonials_item.details["pattern"] == "add_section"
    assert "src/App.jsx" in testimonials_item.details["files"]
    assert "src/components/TestimonialsSection.jsx" in testimonials_item.details["files"]
    assert testimonials_item.details["insert_after"] == "pricing-section"


def test_coder_apply_edit_writes_localized_testimonials_files(tmp_path: Path) -> None:
    task = _sample_editing_task()
    plan = Planner().plan(task)
    result = Coder().code(task, plan, tmp_path / "editing_workspace")

    app_source = (result.workspace_path / "src" / "App.jsx").read_text(encoding="utf-8")
    component_source = (
        result.workspace_path / "src" / "components" / "TestimonialsSection.jsx"
    ).read_text(encoding="utf-8")
    css_source = (result.workspace_path / "src" / "App.css").read_text(encoding="utf-8")

    assert "import { TestimonialsSection }" in app_source
    assert "<TestimonialsSection />" in app_source
    assert app_source.index('className="pricing-section"') < app_source.index("<TestimonialsSection />")
    assert "Maya Chen" in component_source
    assert "Jordan Lee" in component_source
    assert component_source.count("quote:") == 2
    assert ".testimonials-section" in css_source
    assert "src/components/TestimonialsSection.jsx" in result.generated_files


def test_apply_edit_requires_workspace_path() -> None:
    with pytest.raises(ValueError, match="workspace_path is required"):
        Coder().apply_edit(Planner().plan(_sample_editing_task()))


def test_cli_editing_base_smoke_produces_summary() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "webpilot.cli",
            "run",
            "--task",
            "webpilot/tasks/sample_editing_task.json",
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
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["task_id"] == "task_005"
    assert summary["task_type"] == "editing"
    assert summary["variant"] == "base"
    assert summary["iterations"] == 1
    assert (Path(summary["final_workspace_path"]) / "src" / "components" / "TestimonialsSection.jsx").exists()


def _sample_editing_task() -> Task:
    return Task.load("webpilot/tasks/sample_editing_task.json")
