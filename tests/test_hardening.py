from __future__ import annotations

from pathlib import Path
import shutil

from webpilot.agent.coder import Coder
from webpilot.agent.planner import Planner
from webpilot.agent.repairer import Repairer
from webpilot.evaluation.metrics import patch_quality
from webpilot.task_schema import Task


def test_repairer_wires_nav_menu_state(tmp_path: Path) -> None:
    source = Path("webpilot/examples/buggy_nav_app")
    workspace = tmp_path / "nav_workspace"
    shutil.copytree(source, workspace)

    result = Repairer().repair({"likely_failure_types": ["nav_menu_no_state_toggle"]}, workspace)
    app_source = (workspace / "src" / "App.jsx").read_text(encoding="utf-8")

    assert result["repairs_applied"] == ["nav_menu_no_state_toggle"]
    assert "useState" in app_source
    assert "setMenuOpen((open) => !open)" in app_source
    assert 'className={menuOpen ? "nav-menu open" : "nav-menu"}' in app_source


def test_mock_coder_generates_dashboard_components(tmp_path: Path) -> None:
    task = Task.load("webpilot/tasks/sample_dashboard_generation.json")
    plan = Planner().plan(task)
    result = Coder().code(task, plan, tmp_path / "dashboard_workspace")

    names = {item.name for item in plan.items}
    assert {"Sidebar", "StatsBar", "DataTable"}.issubset(names)
    assert (result.workspace_path / "src" / "components" / "Sidebar.jsx").exists()
    assert (result.workspace_path / "src" / "components" / "StatsBar.jsx").exists()
    table_source = (result.workspace_path / "src" / "components" / "DataTable.jsx").read_text(encoding="utf-8")
    assert "<table>" in table_source
    assert table_source.count("account:") == 3


def test_newsletter_edit_pattern_writes_component(tmp_path: Path) -> None:
    task = Task.load("webpilot/tasks/sample_editing_newsletter.json")
    plan = Planner().plan(task)
    result = Coder().code(task, plan, tmp_path / "newsletter_workspace")

    app_source = (result.workspace_path / "src" / "App.jsx").read_text(encoding="utf-8")
    newsletter_source = (
        result.workspace_path / "src" / "components" / "NewsletterSignup.jsx"
    ).read_text(encoding="utf-8")

    assert "NewsletterSignup" in {item.name for item in plan.items}
    assert "<NewsletterSignup />" in app_source
    assert app_source.index("<NewsletterSignup />") < app_source.index('className="contact-section"')
    assert 'name="email"' in newsletter_source
    assert "Subscribe" in newsletter_source


def test_patch_quality_returns_numeric_for_repair_and_editing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "App.jsx").write_text("export default function App() { return null; }\n", encoding="utf-8")
    (workspace / "src" / "App.css").write_text("body { margin: 0; }\n", encoding="utf-8")

    repair_score = patch_quality(
        "diagnostic_repair",
        workspace,
        ["src/App.jsx", "src/App.css"],
        [
            {
                "repairs_applied": ["nav_menu_no_state_toggle"],
                "files_modified": [str(workspace / "src" / "App.jsx")],
                "diffs": {str(workspace / "src" / "App.jsx"): "--- a\n+++ b\n-old\n+new\n"},
            }
        ],
    )
    editing_score = patch_quality(
        "editing",
        workspace,
        ["src/App.jsx", "src/App.css", "src/components/NewsletterSignup.jsx"],
        [],
    )

    assert repair_score is not None and 0.0 <= repair_score <= 1.0
    assert editing_score is not None and 0.0 <= editing_score <= 1.0
    assert patch_quality("text_generation", workspace, ["src/App.jsx"], []) is None
