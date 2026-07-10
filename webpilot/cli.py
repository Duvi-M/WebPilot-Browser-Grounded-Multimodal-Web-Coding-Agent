"""Command line interface for WebPilot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from webpilot.agent.loop import AgentLoop
from webpilot.llm.base import LLMProviderError
from webpilot.llm.mock_provider import MockLLMProvider
from webpilot.llm.openai_provider import OpenAIProvider
from webpilot.task_schema import Task


def main() -> None:
    parser = argparse.ArgumentParser(prog="webpilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a single WebPilot task.")
    run_parser.add_argument("--task", required=True, help="Path to a task JSON file.")
    run_parser.add_argument("--variant", choices=["base", "browser-feedback"], default="base")
    run_parser.add_argument("--max-iterations", type=int, default=1)
    run_parser.add_argument("--llm-provider", choices=["mock", "openai"], default="mock")

    args = parser.parse_args()

    if args.command == "run":
        try:
            run_task(
                Path(args.task),
                variant=args.variant,
                max_iterations=args.max_iterations,
                llm_provider_name=args.llm_provider,
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
        except LLMProviderError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
        except ImportError as exc:
            print(f"Error: missing dependency: {exc}", file=sys.stderr)
            raise SystemExit(1) from None


def run_task(task_path: Path, variant: str = "base", max_iterations: int = 1, llm_provider_name: str = "mock") -> None:
    if not task_path.exists():
        raise FileNotFoundError(f"Task file does not exist: {task_path}")
    llm_provider = _create_llm_provider(llm_provider_name)
    task = Task.load(task_path)
    result = AgentLoop(variant=variant, max_iterations=max_iterations, llm_provider=llm_provider).run(task)  # type: ignore[arg-type]

    print(f"Generated workspace: {result.workspace_path}")
    print(f"Summary: {result.summary_path}")


def _create_llm_provider(name: str):
    if name == "mock":
        return MockLLMProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unsupported LLM provider: {name}")


if __name__ == "__main__":
    main()
