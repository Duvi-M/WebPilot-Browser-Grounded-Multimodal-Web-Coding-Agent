"""Batch evaluation runner for WebPilot tasks."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from webpilot.agent.loop import AgentLoop
from webpilot.config import DEFAULT_RUNS_DIR
from webpilot.task_schema import Task


def main() -> None:
    parser = argparse.ArgumentParser(prog="webpilot-evaluation")
    parser.add_argument("--tasks-dir", required=True)
    parser.add_argument("--variant", choices=["base", "browser-feedback"], default="base")
    parser.add_argument("--max-iterations", type=int, default=1)
    args = parser.parse_args()

    try:
        output_dir = run_evaluation(Path(args.tasks_dir), args.variant, args.max_iterations)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"Evaluation output: {output_dir}")


def run_evaluation(tasks_dir: Path, variant: str, max_iterations: int) -> Path:
    if not tasks_dir.exists() or not tasks_dir.is_dir():
        raise ValueError(f"Tasks directory does not exist: {tasks_dir}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = DEFAULT_RUNS_DIR / "evaluation" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for task_file in sorted(tasks_dir.glob("*.json")):
        task = Task.load(task_file)
        result = AgentLoop(variant=variant, max_iterations=max_iterations).run(task)
        summary = result.summary
        rows.append(
            {
                "task_id": summary["task_id"],
                "type": summary["task_type"],
                "variant": summary["variant"],
                "executability": summary["executability_status"],
                "interaction_correctness": summary["interaction_correctness_score"],
                "patch_quality": summary.get("patch_quality"),
                "iterations": summary["iterations"],
                "final_status": summary["final_status"],
                "summary_path": str(result.summary_path),
            }
        )

    (output_dir / "evaluation_summary.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "evaluation_summary.md").write_text(_markdown(rows), encoding="utf-8")
    return output_dir


def _markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| task_id | type | variant | executability | interaction_correctness | patch_quality | iterations | final_status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        patch_score = row["patch_quality"]
        patch_text = "None" if patch_score is None else f"{patch_score:.4f}"
        lines.append(
            f"| {row['task_id']} | {row['type']} | {row['variant']} | {row['executability']} | "
            f"{row['interaction_correctness']:.2f} | {patch_text} | {row['iterations']} | {row['final_status']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
