"""Deterministic planner for WebPilot."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from webpilot.llm.base import LLMProvider, LLMProviderError
from webpilot.llm.mock_provider import MockLLMProvider
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
    """Builds a structured plan from task text."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or MockLLMProvider()

    def plan(self, task: Task) -> Plan:
        if _uses_llm(self.llm_provider):
            return self._plan_with_llm(task)
        if task.type == "text_generation":
            return self._plan_generation(task)
        if task.type == "editing":
            return self._plan_editing(task)
        return self._plan_repair(task)

    def _plan_with_llm(self, task: Task) -> Plan:
        prompt = _plan_prompt(task, retry=False)
        try:
            return _parse_plan_json(self.llm_provider.complete(prompt))
        except (json.JSONDecodeError, ValueError, LLMProviderError) as first_error:
            retry_prompt = _plan_prompt(task, retry=True, previous_error=str(first_error))
            try:
                return _parse_plan_json(self.llm_provider.complete(retry_prompt))
            except (json.JSONDecodeError, ValueError, LLMProviderError) as second_error:
                raise LLMProviderError(f"LLM planner returned invalid plan JSON after retry: {second_error}") from second_error

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
        if _mentions(source, "dashboard", "data table", "stats"):
            if _mentions(source, "dashboard", "sidebar", "navigation"):
                items.append(
                    PlanItem(
                        name="Sidebar",
                        kind="component",
                        details={"purpose": "Provide dashboard navigation links."},
                    )
                )
            if _mentions(source, "dashboard", "stats", "summary"):
                items.append(
                    PlanItem(
                        name="StatsBar",
                        kind="component",
                        details={"purpose": "Show summary dashboard metrics at the top."},
                    )
                )
            if _mentions(source, "dashboard", "data table", "table", "rows"):
                items.append(
                    PlanItem(
                        name="DataTable",
                        kind="component",
                        details={"rows": 3, "purpose": "Render a data table with real placeholder records."},
                    )
                )
            if not any(item.name == "DashboardShell" for item in items):
                items.append(
                    PlanItem(
                        name="DashboardShell",
                        kind="component",
                        details={"purpose": "Lay out dashboard navigation and main content."},
                    )
                )

        if _mentions(source, "blog", "article", "related posts", "sidebar of related"):
            items.append(
                PlanItem(
                    name="ArticleLayout",
                    kind="component",
                    details={"purpose": "Render a blog-style article with readable sections."},
                )
            )
            items.append(
                PlanItem(
                    name="RelatedPosts",
                    kind="component",
                    details={"purpose": "Show a sidebar of related posts."},
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

    def _plan_editing(self, task: Task) -> Plan:
        source = _task_text(task)
        items: list[PlanItem] = []

        if _mentions(source, "testimonial", "quote", "customer"):
            items.append(
                PlanItem(
                    name="TestimonialsSection",
                    kind="edit_target",
                    details={
                        "pattern": "add_section",
                        "files": [
                            "src/App.jsx",
                            "src/App.css",
                            "src/components/TestimonialsSection.jsx",
                        ],
                        "insert_after": "pricing-section",
                        "items": 2,
                    },
                )
            )
        if _mentions(source, "faq", "frequently asked", "questions"):
            items.append(
                PlanItem(
                    name="FAQSection",
                    kind="edit_target",
                    details={
                        "pattern": "add_section",
                        "files": ["src/App.jsx", "src/App.css", "src/components/FAQSection.jsx"],
                        "insert_before": "contact-section",
                        "items": 3,
                    },
                )
            )
        if _mentions(source, "newsletter", "signup", "sign up", "subscribe"):
            items.append(
                PlanItem(
                    name="NewsletterSignup",
                    kind="edit_target",
                    details={
                        "pattern": "add_newsletter_form",
                        "files": ["src/App.jsx", "src/App.css", "src/components/NewsletterSignup.jsx"],
                        "insert_before": "contact-section",
                        "fields": ["email"],
                    },
                )
            )
        if _mentions(source, "secondary cta", "secondary call to action", "secondary button"):
            items.append(
                PlanItem(
                    name="SecondaryCTAButton",
                    kind="edit_target",
                    details={
                        "pattern": "add_secondary_cta",
                        "files": ["src/App.jsx", "src/App.css"],
                        "label": "View case studies",
                    },
                )
            )
        if _mentions(source, "change", "update") and _mentions(source, "cta", "button") and _mentions(source, "text", "label", "color"):
            items.append(
                PlanItem(
                    name="CTAStyleUpdate",
                    kind="edit_target",
                    details={
                        "pattern": "change_cta_text_color",
                        "files": ["src/App.jsx", "src/App.css"],
                        "label": "Start free today",
                        "color": "#1f5eff",
                    },
                )
            )
        if (
            _mentions(source, "button", "cta", "call to action")
            and not _mentions(source, "newsletter", "signup", "sign up", "subscribe")
            and not _mentions(source, "secondary cta", "secondary call to action", "secondary button")
        ):
            items.append(
                PlanItem(
                    name="CTAButton",
                    kind="edit_target",
                    details={
                        "pattern": "add_button",
                        "files": ["src/App.jsx"],
                        "label": "Get started",
                    },
                )
            )

        if not items:
            items.append(
                PlanItem(
                    name="ManualEditFallback",
                    kind="edit_target",
                    details={
                        "pattern": "unsupported",
                        "files": ["src/App.jsx"],
                        "reason": "No deterministic editing pattern matched this instruction.",
                    },
                )
            )

        rationale = "Editing plan derived deterministically from requested-change keywords and expected behaviors."
        return Plan(task_type=task.type, items=items, rationale=rationale)


def _task_text(task: Task) -> str:
    return " ".join([task.instruction, *task.expected_behaviors, *task.test_hints]).lower()


def _mentions(source: str, *keywords: str) -> bool:
    return any(keyword in source for keyword in keywords)


def _uses_llm(provider: LLMProvider) -> bool:
    return getattr(provider, "provider_name", "mock") != "mock"


def _plan_prompt(task: Task, retry: bool, previous_error: str | None = None) -> str:
    retry_text = ""
    if retry:
        retry_text = f"\nThe previous response was invalid: {previous_error}\nReturn valid JSON only."
    return f"""Create a WebPilot plan for this task.

Return JSON only with exactly this schema:
{{
  "task_type": "text_generation, diagnostic_repair, or editing",
  "items": [
    {{"name": "ComponentOrTargetName", "kind": "component or inspection_target", "details": {{"purpose": "short text"}}}}
  ],
  "rationale": "short rationale"
}}

Task:
{json.dumps(task.to_dict(), indent=2)}
{retry_text}
"""


def _parse_plan_json(raw: str) -> Plan:
    data = json.loads(_strip_json_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("plan must be a JSON object")
    task_type = data.get("task_type")
    items_raw = data.get("items")
    rationale = data.get("rationale")
    if not isinstance(task_type, str) or not task_type:
        raise ValueError("plan.task_type must be a non-empty string")
    if not isinstance(rationale, str) or not rationale:
        raise ValueError("plan.rationale must be a non-empty string")
    if not isinstance(items_raw, list) or not items_raw:
        raise ValueError("plan.items must be a non-empty list")

    items: list[PlanItem] = []
    for item in items_raw:
        if not isinstance(item, dict):
            raise ValueError("each plan item must be an object")
        name = item.get("name")
        kind = item.get("kind")
        details = item.get("details")
        if not isinstance(name, str) or not name:
            raise ValueError("plan item name must be a non-empty string")
        if not isinstance(kind, str) or not kind:
            raise ValueError("plan item kind must be a non-empty string")
        if not isinstance(details, dict):
            raise ValueError("plan item details must be an object")
        items.append(PlanItem(name=name, kind=kind, details=details))
    return Plan(task_type=task_type, items=items, rationale=rationale)


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text
