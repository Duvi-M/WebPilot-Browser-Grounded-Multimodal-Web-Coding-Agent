"""Agent interfaces shared by deterministic and LLM-backed components."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from webpilot.agent.planner import Plan
from webpilot.browser.executor import ExecutionEvidence
from webpilot.task_schema import Task


@dataclass(frozen=True)
class RetrievedContext:
    """Context chunk reserved for future retrieval-augmented prompting."""

    source: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRuntimeContext:
    """Run-scoped context passed to agents without coupling them to the model provider."""

    run_dir: Path
    iteration_dir: Path
    workspace_path: Path | None = None
    retrieved_context: list[RetrievedContext] = field(default_factory=list)
    previous_iteration_summary: dict[str, Any] | None = None


class PlanningAgent(Protocol):
    def plan(self, task: Task) -> Plan:
        """Return a structured implementation or inspection plan."""


class CodingAgent(Protocol):
    def code(self, task: Task, plan: Plan, workspace_path: Path) -> Any:
        """Create or modify a task workspace."""


class ReflectionAgent(Protocol):
    def reflect(self, evidence: ExecutionEvidence, test_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize execution failures and likely repair strategy."""


class RepairAgent(Protocol):
    def repair(self, reflection: dict[str, Any], workspace_path: Path) -> dict[str, Any]:
        """Apply a targeted repair to a workspace."""


class RetrievalService(Protocol):
    def retrieve(self, task: Task, phase: str, context: AgentRuntimeContext) -> list[RetrievedContext]:
        """Return optional context chunks before an LLM prompt is built."""
