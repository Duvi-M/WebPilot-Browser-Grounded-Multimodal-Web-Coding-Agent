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
    run_parser.add_argument("--dry-run-llm", action="store_true", help="Log OpenAI prompts without calling the API.")
    run_parser.add_argument("--max-llm-calls", type=int, default=None, help="Maximum real OpenAI calls for this run.")
    run_parser.add_argument("--llm-coder", action="store_true", help="Use the selected LLM provider for coding with fallback.")
    run_parser.add_argument("--llm-reflector", action="store_true", help="Use the selected LLM provider for reflection with fallback.")
    run_parser.add_argument("--llm-repair", action="store_true", help="Use the selected LLM provider for repair with fallback.")

    args = parser.parse_args()

    if args.command == "run":
        try:
            run_task(
                Path(args.task),
                variant=args.variant,
                max_iterations=args.max_iterations,
                llm_provider_name=args.llm_provider,
                dry_run_llm=args.dry_run_llm,
                max_llm_calls=args.max_llm_calls,
                llm_coder=args.llm_coder,
                llm_reflector=args.llm_reflector,
                llm_repair=args.llm_repair,
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


def run_task(
    task_path: Path,
    variant: str = "base",
    max_iterations: int = 1,
    llm_provider_name: str = "mock",
    dry_run_llm: bool = False,
    max_llm_calls: int | None = None,
    llm_coder: bool = False,
    llm_reflector: bool = False,
    llm_repair: bool = False,
) -> None:
    if not task_path.exists():
        raise FileNotFoundError(f"Task file does not exist: {task_path}")
    if max_llm_calls is not None and max_llm_calls < 0:
        raise ValueError("--max-llm-calls must be 0 or greater")
    llm_provider = _create_llm_provider(llm_provider_name, dry_run_llm=dry_run_llm, max_llm_calls=max_llm_calls)
    task = Task.load(task_path)
    result = AgentLoop(
        variant=variant,
        max_iterations=max_iterations,
        llm_provider=llm_provider,
        llm_coder=llm_coder,
        llm_reflector=llm_reflector,
        llm_repair=llm_repair,
    ).run(task)  # type: ignore[arg-type]

    print(f"Generated workspace: {result.workspace_path}")
    print(f"Summary: {result.summary_path}")


def _create_llm_provider(name: str, dry_run_llm: bool = False, max_llm_calls: int | None = None):
    if name == "mock":
        return MockLLMProvider()
    if name == "openai":
        budget = 1 if max_llm_calls is None else max_llm_calls
        return OpenAIProvider(dry_run=dry_run_llm, max_llm_calls=budget)
    raise ValueError(f"Unsupported LLM provider: {name}")


if __name__ == "__main__":
    main()
