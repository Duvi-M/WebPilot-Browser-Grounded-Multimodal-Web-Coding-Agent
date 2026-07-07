"""Command line interface for WebPilot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from webpilot.agent.loop import AgentLoop
from webpilot.task_schema import Task


def main() -> None:
    parser = argparse.ArgumentParser(prog="webpilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a single WebPilot task.")
    run_parser.add_argument("--task", required=True, help="Path to a task JSON file.")
    run_parser.add_argument("--variant", choices=["base", "browser-feedback"], default="base")
    run_parser.add_argument("--max-iterations", type=int, default=1)

    args = parser.parse_args()

    if args.command == "run":
        try:
            run_task(Path(args.task), variant=args.variant, max_iterations=args.max_iterations)
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
        except ImportError as exc:
            print(f"Error: missing dependency: {exc}", file=sys.stderr)
            raise SystemExit(1) from None


def run_task(task_path: Path, variant: str = "base", max_iterations: int = 1) -> None:
    if not task_path.exists():
        raise FileNotFoundError(f"Task file does not exist: {task_path}")
    task = Task.load(task_path)
    result = AgentLoop(variant=variant, max_iterations=max_iterations).run(task)  # type: ignore[arg-type]

    print(f"Generated workspace: {result.workspace_path}")
    print(f"Summary: {result.summary_path}")


if __name__ == "__main__":
    main()
