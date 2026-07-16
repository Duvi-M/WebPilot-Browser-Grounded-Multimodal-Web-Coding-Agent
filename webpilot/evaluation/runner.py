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
from webpilot.llm.mock_provider import MockLLMProvider
from webpilot.llm.openai_provider import OpenAIProvider
from webpilot.task_schema import Task


def main() -> None:
    parser = argparse.ArgumentParser(prog="webpilot-evaluation")
    parser.add_argument("--tasks-dir", required=True)
    parser.add_argument("--variant", choices=["base", "browser-feedback"], default="base")
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--llm-provider", choices=["mock", "openai"], default="mock")
    parser.add_argument("--allow-paid-batch", action="store_true")
    parser.add_argument("--dry-run-llm", action="store_true")
    parser.add_argument("--max-llm-calls", type=int, default=None)
    args = parser.parse_args()

    try:
        output_dir = run_evaluation(
            Path(args.tasks_dir),
            args.variant,
            args.max_iterations,
            llm_provider_name=args.llm_provider,
            allow_paid_batch=args.allow_paid_batch,
            dry_run_llm=args.dry_run_llm,
            max_llm_calls=args.max_llm_calls,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"Evaluation output: {output_dir}")


def run_evaluation(
    tasks_dir: Path,
    variant: str,
    max_iterations: int,
    llm_provider_name: str = "mock",
    allow_paid_batch: bool = False,
    dry_run_llm: bool = False,
    max_llm_calls: int | None = None,
) -> Path:
    if not tasks_dir.exists() or not tasks_dir.is_dir():
        raise ValueError(f"Tasks directory does not exist: {tasks_dir}")
    if llm_provider_name == "openai" and not allow_paid_batch:
        raise ValueError("OpenAI evaluation batch requires --allow-paid-batch")
    if max_llm_calls is not None and max_llm_calls < 0:
        raise ValueError("--max-llm-calls must be 0 or greater")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = DEFAULT_RUNS_DIR / "evaluation" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for task_file in sorted(tasks_dir.glob("*.json")):
        task = Task.load(task_file)
        result = AgentLoop(
            variant=variant,
            max_iterations=max_iterations,
            llm_provider=_create_llm_provider(llm_provider_name, dry_run_llm, max_llm_calls),
        ).run(task)
        summary = result.summary
        rows.append(
            {
                "task_id": summary["task_id"],
                "type": summary["task_type"],
                "variant": summary["variant"],
                "executability": summary["executability_status"],
                "interaction_correctness": summary["interaction_correctness_score"],
                "patch_quality": summary.get("patch_quality"),
                "visual_sanity_score": summary.get("visual_sanity_score"),
                "visual_quality": summary.get("visual_quality"),
                "iterations": summary["iterations"],
                "final_status": summary["final_status"],
                "summary_path": str(result.summary_path),
                "llm_provider": summary.get("llm_provider"),
                "llm_calls_attempted": summary.get("llm_calls_attempted"),
                "llm_calls_completed": summary.get("llm_calls_completed"),
                "dry_run_llm": summary.get("dry_run_llm"),
            }
        )

    (output_dir / "evaluation_summary.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "evaluation_summary.md").write_text(_markdown(rows), encoding="utf-8")
    return output_dir


def _create_llm_provider(name: str, dry_run_llm: bool, max_llm_calls: int | None):
    if name == "mock":
        return MockLLMProvider()
    if name == "openai":
        budget = 1 if max_llm_calls is None else max_llm_calls
        return OpenAIProvider(dry_run=dry_run_llm, max_llm_calls=budget)
    raise ValueError(f"Unsupported LLM provider: {name}")


def _markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| task_id | type | variant | executability | interaction_correctness | patch_quality | visual_sanity_score | visual_quality | iterations | final_status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        patch_score = row["patch_quality"]
        patch_text = "None" if patch_score is None else f"{patch_score:.4f}"
        sanity_score = row["visual_sanity_score"]
        sanity_text = "None" if sanity_score is None else f"{sanity_score:.4f}"
        visual_quality_text = "None" if row["visual_quality"] is None else str(row["visual_quality"])
        lines.append(
            f"| {row['task_id']} | {row['type']} | {row['variant']} | {row['executability']} | "
            f"{row['interaction_correctness']:.2f} | {patch_text} | {sanity_text} | {visual_quality_text} | "
            f"{row['iterations']} | {row['final_status']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
