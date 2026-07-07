from __future__ import annotations

import pytest

from webpilot.task_schema import Task


def test_text_generation_task_loads() -> None:
    task = Task.from_dict(
        {
            "id": "task_001",
            "type": "text_generation",
            "instruction": "Build a landing page.",
            "repo_path": None,
            "expected_behaviors": ["Shows a hero"],
            "test_hints": ["Find heading"],
        }
    )

    assert task.id == "task_001"
    assert task.type == "text_generation"
    assert task.repo_path is None


def test_diagnostic_repair_requires_repo_path() -> None:
    with pytest.raises(ValueError, match="require"):
        Task.from_dict(
            {
                "id": "task_002",
                "type": "diagnostic_repair",
                "instruction": "Fix a bug.",
                "repo_path": None,
                "expected_behaviors": [],
                "test_hints": [],
            }
        )


def test_unsupported_task_type_fails() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        Task.from_dict({"id": "bad", "type": "other", "instruction": "Nope"})

