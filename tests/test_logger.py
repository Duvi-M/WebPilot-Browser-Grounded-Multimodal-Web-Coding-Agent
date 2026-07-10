from __future__ import annotations

import json
from pathlib import Path

from webpilot.logging_utils.run_logger import RunLogger
from webpilot.task_schema import Task


def test_logger_writes_iteration_and_summary(tmp_path: Path) -> None:
    task = Task(
        id="task_log",
        type="text_generation",
        instruction="Build a hero section.",
        repo_path=None,
        expected_behaviors=[],
        test_hints=[],
    )
    logger = RunLogger(runs_dir=tmp_path)
    paths = logger.create_run(task)

    logger.write_plan(paths, {"task_type": task.type, "items": [], "rationale": "test"})
    logger.write_generated_files(paths, ["package.json"])
    summary = logger.write_summary(
        paths,
        {
            "task_id": task.id,
            "task_type": task.type,
            "variant": "base",
            "iterations": 1,
            "status": "generated",
            "final_status": "failed",
            "artifact_paths": {"run_dir": str(paths.run_dir)},
        },
    )

    assert paths.plan_path.exists()
    assert paths.generated_files_path.exists()
    assert paths.summary_path.exists()
    assert summary["status"] == "generated"
    assert summary["final_status"] == "failed"

    generated = json.loads(paths.generated_files_path.read_text(encoding="utf-8"))
    assert generated == {"files": ["package.json"]}
