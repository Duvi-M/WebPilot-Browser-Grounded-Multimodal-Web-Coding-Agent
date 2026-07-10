from __future__ import annotations

from pathlib import Path

import pytest

from webpilot.agent.coder import Coder
from webpilot.agent.planner import Planner
from webpilot.task_schema import Task


def test_planner_detects_landing_page_sections() -> None:
    task = _sample_task()
    plan = Planner().plan(task)
    names = {item.name for item in plan.items}

    assert {"HeroSection", "PricingSection", "ContactForm"}.issubset(names)


def test_coder_generates_real_vite_react_app(tmp_path: Path) -> None:
    task = _sample_task()
    plan = Planner().plan(task)
    result = Coder().code(task, plan, tmp_path / "generated_workspace")

    app_jsx = result.workspace_path / "src" / "App.jsx"
    contact_form = result.workspace_path / "src" / "components" / "ContactForm.jsx"

    assert (result.workspace_path / "package.json").exists()
    assert app_jsx.exists()
    assert contact_form.exists()
    assert "HeroSection" in app_jsx.read_text(encoding="utf-8")
    assert "PricingSection" in app_jsx.read_text(encoding="utf-8")
    assert "ContactForm" in app_jsx.read_text(encoding="utf-8")

    contact_source = contact_form.read_text(encoding="utf-8")
    assert 'name="name"' in contact_source
    assert 'name="email"' in contact_source
    assert 'name="message"' in contact_source
    assert "src/components/PricingSection.jsx" in result.generated_files


def test_apply_repair_requires_workspace_path() -> None:
    with pytest.raises(ValueError, match="workspace_path is required"):
        Coder().apply_repair({})


def test_apply_repair_delegates_to_repairer(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "App.jsx").write_text(
        """export default function App() {
  return (
    <form>
      <input name="name" />
      <input name="email" />
      <button type="submit">Send</button>
    </form>
  );
}
""",
        encoding="utf-8",
    )
    (workspace / "src" / "App.css").write_text("body { margin: 0; }\n", encoding="utf-8")

    result = Coder().apply_repair(
        {"likely_failure_types": ["missing_form_field", "missing_submit_feedback", "horizontal_overflow_mobile"]},
        workspace,
    )

    assert isinstance(result, dict)
    assert result["repairs_applied"]
    app_source = (workspace / "src" / "App.jsx").read_text(encoding="utf-8")
    assert 'name="message"' in app_source
    assert "Message sent" in app_source
    assert "overflow-x: hidden" in (workspace / "src" / "App.css").read_text(encoding="utf-8")


def test_diagnostic_repair_copies_repo_into_workspace(tmp_path: Path) -> None:
    source_repo = tmp_path / "source_repo"
    source_repo.mkdir()
    (source_repo / "package.json").write_text('{"scripts":{"dev":"vite"}}\n', encoding="utf-8")
    (source_repo / "src").mkdir()
    (source_repo / "src" / "App.jsx").write_text("export default function App() { return null; }\n", encoding="utf-8")

    task = Task(
        id="task_002",
        type="diagnostic_repair",
        instruction="Diagnose why the CTA button does not respond.",
        repo_path=str(source_repo),
        expected_behaviors=["The CTA button should respond to clicks."],
        test_hints=[],
    )
    plan = Planner().plan(task)
    result = Coder().code(task, plan, tmp_path / "repair_workspace")

    assert (result.workspace_path / "package.json").exists()
    assert (result.workspace_path / "src" / "App.jsx").exists()
    assert "src/App.jsx" in result.generated_files


def _sample_task() -> Task:
    return Task(
        id="task_001",
        type="text_generation",
        instruction="Build a responsive landing page for a task management app with a hero section, pricing cards, and a contact form.",
        repo_path=None,
        expected_behaviors=[
            "The page includes a hero section with a clear CTA button.",
            "The page includes pricing cards for multiple plans.",
            "The page includes a contact form with name, email, and message inputs.",
        ],
        test_hints=[],
    )
