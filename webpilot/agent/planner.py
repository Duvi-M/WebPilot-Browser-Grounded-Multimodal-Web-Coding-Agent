"""Deterministic planner for WebPilot step 1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from webpilot.task_schema import Task


@dataclass(frozen=True)
class PlanItem:
    name: str
    kind: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "details": self.details}


@dataclass(frozen=True)
class Plan:
    task_type: str
    items: list[PlanItem]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "items": [item.to_dict() for item in self.items],
            "rationale": self.rationale,
        }


class Planner:
    """Builds a structured, deterministic plan from task text."""

    def plan(self, task: Task) -> Plan:
        if task.type == "text_generation":
            return self._plan_generation(task)
        return self._plan_repair(task)

    def _plan_generation(self, task: Task) -> Plan:
        source = _task_text(task)
        items: list[PlanItem] = []

        if _mentions(source, "hero", "landing"):
            items.append(
                PlanItem(
                    name="HeroSection",
                    kind="component",
                    details={"purpose": "Introduce the product and show a primary CTA button."},
                )
            )
        if _mentions(source, "pricing", "price", "plan"):
            items.append(
                PlanItem(
                    name="PricingSection",
                    kind="component",
                    details={"tiers": ["Starter", "Pro", "Team"], "purpose": "Show pricing cards."},
                )
            )
        if _mentions(source, "contact", "form", "email", "message"):
            items.append(
                PlanItem(
                    name="ContactForm",
                    kind="component",
                    details={"fields": ["name", "email", "message"], "purpose": "Collect contact details."},
                )
            )

        if not items:
            items.append(
                PlanItem(
                    name="AppShell",
                    kind="component",
                    details={"purpose": "Render the requested page structure."},
                )
            )

        rationale = "Plan derived deterministically from instruction keywords and expected behaviors."
        return Plan(task_type=task.type, items=items, rationale=rationale)

    def _plan_repair(self, task: Task) -> Plan:
        source = _task_text(task)
        targets: list[PlanItem] = []

        if _mentions(source, "button", "click", "cta"):
            targets.append(
                PlanItem(
                    name="InteractiveControls",
                    kind="inspection_target",
                    details={"focus": "Buttons, click handlers, and user-triggered state changes."},
                )
            )
        if _mentions(source, "layout", "overflow", "responsive", "visual"):
            targets.append(
                PlanItem(
                    name="LayoutAndStyles",
                    kind="inspection_target",
                    details={"focus": "CSS, responsive behavior, overflow, and visual alignment."},
                )
            )
        if _mentions(source, "console", "error", "runtime"):
            targets.append(
                PlanItem(
                    name="RuntimeErrors",
                    kind="inspection_target",
                    details={"focus": "Build/runtime errors and console output."},
                )
            )
        if not targets:
            targets.append(
                PlanItem(
                    name="RepositoryStructure",
                    kind="inspection_target",
                    details={"focus": "Files likely related to the diagnostic repair request."},
                )
            )

        rationale = "Repair planning identifies inspection targets only; patching is deferred to step 2."
        return Plan(task_type=task.type, items=targets, rationale=rationale)


def _task_text(task: Task) -> str:
    return " ".join([task.instruction, *task.expected_behaviors, *task.test_hints]).lower()


def _mentions(source: str, *keywords: str) -> bool:
    return any(keyword in source for keyword in keywords)

