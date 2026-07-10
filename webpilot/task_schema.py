"""Task schema for WebPilot."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Literal


TaskType = Literal["text_generation", "diagnostic_repair", "editing"]


@dataclass(frozen=True)
class Task:
    """A WebPilot task loaded from JSON."""

    id: str
    type: TaskType
    instruction: str
    repo_path: str | None = None
    expected_behaviors: list[str] = field(default_factory=list)
    test_hints: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        task_id = _required_string(data, "id")
        task_type = _required_string(data, "type")
        if task_type not in ("text_generation", "diagnostic_repair", "editing"):
            raise ValueError(f"Unsupported task type: {task_type}")

        instruction = _required_string(data, "instruction")
        repo_path = data.get("repo_path")
        if repo_path is not None and not isinstance(repo_path, str):
            raise ValueError("repo_path must be a string or null")

        expected_behaviors = _string_list(data.get("expected_behaviors", []), "expected_behaviors")
        test_hints = _string_list(data.get("test_hints", []), "test_hints")

        if task_type == "text_generation" and repo_path is not None:
            raise ValueError("text_generation tasks must have repo_path set to null")
        if task_type in ("diagnostic_repair", "editing") and not repo_path:
            raise ValueError(f"{task_type} tasks require a non-null repo_path")

        return cls(
            id=task_id,
            type=task_type,  # type: ignore[arg-type]
            instruction=instruction,
            repo_path=repo_path,
            expected_behaviors=expected_behaviors,
            test_hints=test_hints,
        )

    @classmethod
    def load(cls, path: str | Path) -> "Task":
        with Path(path).open("r", encoding="utf-8") as task_file:
            data = json.load(task_file)
        if not isinstance(data, dict):
            raise ValueError("Task file must contain a JSON object")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "instruction": self.instruction,
            "repo_path": self.repo_path,
            "expected_behaviors": self.expected_behaviors,
            "test_hints": self.test_hints,
        }


def _required_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return value
