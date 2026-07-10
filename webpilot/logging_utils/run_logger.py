"""Filesystem logger for WebPilot runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from webpilot.config import DEFAULT_RUNS_DIR
from webpilot.task_schema import Task


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    iteration_dir: Path
    workspace_dir: Path
    plan_path: Path
    generated_files_path: Path
    summary_path: Path


class RunLogger:
    """Creates run directories and writes JSON artifacts."""

    def __init__(self, runs_dir: Path = DEFAULT_RUNS_DIR) -> None:
        self.runs_dir = runs_dir

    def create_run(self, task: Task) -> RunPaths:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = self.runs_dir / task.id / timestamp
        suffix = 1
        while run_dir.exists():
            run_dir = self.runs_dir / task.id / f"{timestamp}-{suffix}"
            suffix += 1

        iteration_dir = run_dir / "iteration_0"
        workspace_dir = run_dir / "generated_workspace"
        iteration_dir.mkdir(parents=True, exist_ok=False)
        workspace_dir.mkdir(parents=True, exist_ok=True)

        return RunPaths(
            run_dir=run_dir,
            iteration_dir=iteration_dir,
            workspace_dir=workspace_dir,
            plan_path=iteration_dir / "plan.json",
            generated_files_path=iteration_dir / "generated_files.json",
            summary_path=run_dir / "summary.json",
        )

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_plan(self, paths: RunPaths, plan: dict[str, Any]) -> None:
        self.write_json(paths.plan_path, plan)

    def write_generated_files(self, paths: RunPaths, files: list[str]) -> None:
        self.write_json(paths.generated_files_path, {"files": files})

    def write_summary(self, paths: RunPaths, summary: dict[str, Any]) -> dict[str, Any]:
        self.write_json(paths.summary_path, summary)
        return summary
