"""WebPilot agent loop orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from webpilot.agent.coder import Coder
from webpilot.agent.planner import Planner
from webpilot.agent.reflector import Reflector
from webpilot.browser.executor import BrowserExecutor, ExecutionEvidence
from webpilot.evaluation.metrics import executability, interaction_correctness
from webpilot.logging_utils.run_logger import RunLogger, RunPaths
from webpilot.llm.base import LLMProvider
from webpilot.llm.mock_provider import MockLLMProvider
from webpilot.task_schema import Task


Variant = Literal["base", "browser-feedback"]


@dataclass(frozen=True)
class AgentRunResult:
    run_dir: Path
    workspace_path: Path
    summary_path: Path
    summary: dict[str, Any]


class AgentLoop:
    """Coordinates plan, code, browser execution, reflection, and optional repair."""

    def __init__(self, variant: Variant = "base", max_iterations: int = 1, llm_provider: LLMProvider | None = None) -> None:
        if max_iterations < 1:
            raise ValueError("--max-iterations must be at least 1")
        self.variant = variant
        self.max_iterations = max_iterations
        self.llm_provider = llm_provider or MockLLMProvider()
        self.logger = RunLogger()
        self.planner = Planner(self.llm_provider)
        self.coder = Coder(self.llm_provider)
        self.executor = BrowserExecutor()
        self.reflector = Reflector()

    def run(self, task: Task) -> AgentRunResult:
        paths = self.logger.create_run(task)
        plan = self.planner.plan(task)
        self.logger.write_plan(paths, plan.to_dict())
        code_result = self.coder.code(task, plan, paths.workspace_dir)
        self.logger.write_generated_files(paths, code_result.generated_files)

        repairs_attempted: list[dict[str, Any]] = []
        artifact_paths: dict[str, Any] = {
            "run_dir": str(paths.run_dir),
            "workspace": str(paths.workspace_dir),
            "plan": str(paths.plan_path),
            "generated_files": str(paths.generated_files_path),
            "iterations": {},
        }
        final_reflection: dict[str, Any] = {"passed": False}
        final_evidence: ExecutionEvidence | None = None
        final_tests: list[dict[str, Any]] = []
        iterations_run = 0

        for index in range(self.max_iterations):
            iteration_dir = _iteration_dir(paths, index)
            if index == 0:
                iteration_dir.mkdir(parents=True, exist_ok=True)
            iterations_run = index + 1
            browser_result = self.executor.execute(paths.workspace_dir, iteration_dir, task)
            final_evidence = browser_result.evidence
            final_tests = [result.to_dict() for result in browser_result.test_results]
            self.logger.write_json(iteration_dir / "test_results.json", {"results": final_tests})
            final_reflection = self.reflector.reflect(browser_result.evidence, final_tests)
            self.logger.write_json(iteration_dir / "reflection.json", final_reflection)
            artifact_paths["iterations"][f"iteration_{index}"] = str(iteration_dir)

            if final_reflection.get("passed"):
                break
            if self.variant == "base":
                break
            if index >= self.max_iterations - 1:
                break

            repair_plan = self.coder.apply_repair(final_reflection, paths.workspace_dir)
            repairs_attempted.append(repair_plan)
            self.logger.write_json(iteration_dir / "repair_plan.json", repair_plan)

        summary = _summary(
            task=task,
            variant=self.variant,
            iterations=iterations_run,
            evidence=final_evidence,
            test_results=final_tests,
            reflection=final_reflection,
            repairs_attempted=repairs_attempted,
            artifact_paths=artifact_paths,
            workspace_path=paths.workspace_dir,
        )
        self.logger.write_json(paths.summary_path, summary)
        return AgentRunResult(paths.run_dir, paths.workspace_dir, paths.summary_path, summary)


def _iteration_dir(paths: RunPaths, index: int) -> Path:
    return paths.run_dir / f"iteration_{index}"


def _summary(
    task: Task,
    variant: str,
    iterations: int,
    evidence: ExecutionEvidence | None,
    test_results: list[dict[str, Any]],
    reflection: dict[str, Any],
    repairs_attempted: list[dict[str, Any]],
    artifact_paths: dict[str, Any],
    workspace_path: Path,
) -> dict[str, Any]:
    executable = executability(evidence)
    interaction_score = interaction_correctness(test_results)
    repairs_applied = [repair for repair in repairs_attempted if repair.get("repairs_applied")]
    if reflection.get("passed"):
        final_status = "passed"
    elif evidence is not None and not executable:
        final_status = "execution_failed"
    elif repairs_applied and iterations >= 1:
        final_status = "repaired_but_unverified" if iterations == 0 else "failed"
    else:
        final_status = "failed"

    return {
        "task_id": task.id,
        "task_type": task.type,
        "variant": variant,
        "iterations": iterations,
        "status": "generated",
        "final_status": final_status,
        "executability_status": "passed" if executable else "failed",
        "interaction_correctness_status": "passed" if interaction_score == 1.0 else "failed",
        "interaction_correctness_score": interaction_score,
        "failures_found": reflection.get("failed_checks", []),
        "repairs_attempted": repairs_attempted,
        "artifact_paths": artifact_paths,
        "final_workspace_path": str(workspace_path),
    }
