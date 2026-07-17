"""Deterministic template-based repairs for known WebPilot MVP failures."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from webpilot.llm.base import LLMProvider, LLMProviderError
from webpilot.llm.mock_provider import MockLLMProvider
from webpilot.task_schema import Task


class Repairer:
    """Applies localized file edits for known browser-feedback failure types."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or MockLLMProvider()

    def repair(
        self,
        reflection: dict[str, Any],
        workspace_path: Path,
        task: Task | None = None,
        artifact_paths: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if _uses_llm(self.llm_provider) and task is not None:
            try:
                return self._repair_with_llm(task, reflection, workspace_path, artifact_paths or {})
            except (json.JSONDecodeError, ValueError, LLMProviderError, OSError) as exc:
                _record_provider_fallback(self.llm_provider, f"LLM repair fallback: {exc}")
        failure_types = _normalize_failure_types(list(reflection.get("likely_failure_types", [])))
        plan: dict[str, Any] = {
            "repairs_attempted": failure_types,
            "repairs_applied": [],
            "files_modified": [],
            "details": [],
            "diffs": {},
            "skipped_repair_types": [],
        }

        for failure_type in failure_types:
            if failure_type == "missing_form_field":
                self._apply_with_record(plan, failure_type, workspace_path, self._repair_missing_fields)
            elif failure_type in {"submit_button_no_handler", "missing_submit_feedback"}:
                self._apply_with_record(plan, failure_type, workspace_path, self._repair_submit_feedback)
            elif failure_type == "horizontal_overflow_mobile":
                self._apply_with_record(plan, failure_type, workspace_path, self._repair_overflow)
            elif failure_type == "nav_menu_no_state_toggle":
                self._apply_with_record(plan, failure_type, workspace_path, self._repair_nav_menu)
            elif failure_type == "tabs_no_state_switch":
                self._apply_with_record(plan, failure_type, workspace_path, self._repair_tabs)
            else:
                plan["skipped_repair_types"].append(failure_type)
                plan["details"].append(f"No automated repair available for {failure_type}.")

        return plan

    def _repair_with_llm(
        self,
        task: Task,
        reflection: dict[str, Any],
        workspace_path: Path,
        artifact_paths: dict[str, Any],
    ) -> dict[str, Any]:
        before = _snapshot_workspace_files(workspace_path)
        prompt = _repair_prompt(task, reflection, before, artifact_paths)
        files = _parse_repair_files(self.llm_provider.complete(prompt))
        if not files:
            raise ValueError("LLM repair returned no files")

        files_touched: list[str] = []
        for relative_path, content in files.items():
            target = _safe_workspace_path(workspace_path, relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            files_touched.append(relative_path)

        touched = sorted(set(files_touched))
        diffs = _diff_touched_files(workspace_path, before, touched)
        if not diffs:
            raise ValueError("LLM repair did not modify any files")
        return {
            "repairs_attempted": ["llm_repair"],
            "repairs_applied": ["llm_repair"],
            "files_modified": [str((workspace_path / path).resolve()) for path in touched if path in diffs],
            "details": ["Applied LLM full-file repair."],
            "diffs": {str((workspace_path / path).resolve()): diff for path, diff in diffs.items()},
            "skipped_repair_types": [],
            "llm_repair": True,
        }

    def _apply_with_record(self, plan: dict[str, Any], repair_type: str, workspace_path: Path, repair: Any) -> None:
        changed, files, details, diffs = repair(workspace_path)
        if changed:
            plan["repairs_applied"].append(repair_type)
            plan["files_modified"].extend(file for file in files if file not in plan["files_modified"])
            plan["details"].extend(details)
            plan["diffs"].update(diffs)
        else:
            plan["skipped_repair_types"].append(repair_type)
            plan["details"].extend(details or [f"No changes needed for {repair_type}."])

    def _repair_missing_fields(self, workspace_path: Path) -> tuple[bool, list[str], list[str], dict[str, str]]:
        target = _find_form_file(workspace_path)
        if target is None:
            return False, [], ["No React file containing a form was found."], {}

        before = target.read_text(encoding="utf-8")
        after = before
        inserts: list[str] = []
        lower = before.lower()
        if 'name="name"' not in lower:
            inserts.append(
                '<label>\n'
                '  Name\n'
                '  <input name="name" type="text" placeholder="Alex Morgan" autoComplete="name" />\n'
                '</label>'
            )
        if 'name="email"' not in lower and 'type="email"' not in lower:
            inserts.append(
                '<label>\n'
                '  Email\n'
                '  <input name="email" type="email" placeholder="alex@example.com" autoComplete="email" />\n'
                '</label>'
            )
        if 'name="message"' not in lower:
            inserts.append(
                '<label>\n'
                '  Message\n'
                '  <textarea name="message" placeholder="How can we help?" rows="5" />\n'
                '</label>'
            )

        if inserts:
            after = _insert_before_first_form_button(after, "\n".join(inserts))

        return _write_if_changed(target, before, after, "Added missing form fields.")

    def _repair_submit_feedback(self, workspace_path: Path) -> tuple[bool, list[str], list[str], dict[str, str]]:
        target = _find_form_file(workspace_path)
        if target is None:
            return False, [], ["No React file containing a form was found."], {}

        before = target.read_text(encoding="utf-8")
        after = before
        if "useState" not in after:
            if "import React from 'react';" in after:
                after = after.replace("import React from 'react';", "import React, { useState } from 'react';", 1)
            elif "from 'react'" in after and "useState" not in after:
                after = after.replace("import {", "import { useState,", 1)
            else:
                after = "import { useState } from 'react';\n" + after

        if "const [submitted, setSubmitted]" not in after:
            after = _insert_after_function_open(after, "  const [submitted, setSubmitted] = useState(false);\n\n  function handleSubmit(event) {\n    event.preventDefault();\n    setSubmitted(true);\n  }\n")

        if "<form" in after and "onSubmit={handleSubmit}" not in after:
            after = after.replace("<form", "<form onSubmit={handleSubmit}", 1)

        if "Message sent" not in after:
            after = _insert_before_first_form_close(
                after,
                '{submitted && <p role="status" className="form-status">Message sent</p>}',
            )

        return _write_if_changed(target, before, after, "Added submit handler and visible confirmation feedback.")

    def _repair_overflow(self, workspace_path: Path) -> tuple[bool, list[str], list[str], dict[str, str]]:
        target = workspace_path / "src" / "App.css"
        if not target.exists():
            return False, [], ["src/App.css was not found."], {}

        before = target.read_text(encoding="utf-8")
        after = before
        rules = """

html,
body {
  overflow-x: hidden;
  max-width: 100%;
}

img,
video,
canvas,
svg {
  max-width: 100%;
}

.wide-banner,
.overflow-strip {
  max-width: 100%;
  width: 100%;
}
"""
        if "overflow-x: hidden" not in after:
            after = after.rstrip() + rules + "\n"
        return _write_if_changed(target, before, after, "Added mobile horizontal overflow guards.")

    def _repair_nav_menu(self, workspace_path: Path) -> tuple[bool, list[str], list[str], dict[str, str]]:
        target = _find_nav_file(workspace_path)
        if target is None:
            return False, [], ["No React file containing a nav menu toggle was found."], {}

        before = target.read_text(encoding="utf-8")
        after = before
        if "useState" not in after:
            if "import React from 'react';" in after:
                after = after.replace("import React from 'react';", "import React, { useState } from 'react';", 1)
            elif "from 'react'" in after and "useState" not in after:
                after = after.replace("import {", "import { useState,", 1)
            else:
                after = "import { useState } from 'react';\n" + after

        if "const [menuOpen, setMenuOpen]" not in after:
            after = _insert_after_function_open(
                after,
                "  const [menuOpen, setMenuOpen] = useState(false);\n",
            )

        if "function handleMenuClick()" in after and "setMenuOpen((open) => !open)" not in after:
            after = _replace_function_body(
                after,
                "handleMenuClick",
                "  function handleMenuClick() {\n    setMenuOpen((open) => !open);\n  }",
            )
        elif "function handleMenuClick()" not in after:
            after = _insert_after_function_open(
                after,
                "\n  function handleMenuClick() {\n    setMenuOpen((open) => !open);\n  }\n",
            )

        after = after.replace('className="nav-menu"', 'className={menuOpen ? "nav-menu open" : "nav-menu"}', 1)
        after = after.replace('aria-label="Primary navigation"', 'aria-label="Primary navigation" role="menu"', 1)
        after = after.replace('aria-label="Open menu"', 'aria-label="Open menu" aria-expanded={menuOpen}', 1)

        return _write_if_changed(target, before, after, "Wired nav menu toggle to React state and visible menu class.")

    def _repair_tabs(self, workspace_path: Path) -> tuple[bool, list[str], list[str], dict[str, str]]:
        target = _find_tabs_file(workspace_path)
        if target is None:
            return False, [], ["No React file containing a tab switcher was found."], {}

        before = target.read_text(encoding="utf-8")
        after = before
        if "useState" not in after:
            if "import React from 'react';" in after:
                after = after.replace("import React from 'react';", "import React, { useState } from 'react';", 1)
            elif "from 'react'" in after and "useState" not in after:
                after = after.replace("import {", "import { useState,", 1)
            else:
                after = "import { useState } from 'react';\n" + after

        if "const [activeTab, setActiveTab]" not in after:
            after = _insert_after_function_open(after, "  const [activeTab, setActiveTab] = useState('overview');\n")

        replacements = {
            'aria-selected="true" onClick={handleTabClick}': 'aria-selected={activeTab === "overview"} onClick={() => setActiveTab("overview")}',
            'aria-selected="false" onClick={handleTabClick}': 'aria-selected={activeTab === "details"} onClick={() => setActiveTab("details")}',
            'className="tab-panel panel-active" role="tabpanel"': 'className={activeTab === "overview" ? "tab-panel panel-active" : "tab-panel"} role="tabpanel" hidden={activeTab !== "overview"}',
            'className="tab-panel" hidden': 'className={activeTab === "details" ? "tab-panel panel-active" : "tab-panel"} hidden={activeTab !== "details"}',
            'className="tab-panel" role="tabpanel" hidden': 'className={activeTab === "details" ? "tab-panel panel-active" : "tab-panel"} role="tabpanel" hidden={activeTab !== "details"}',
            'hidden={true}': 'hidden={activeTab !== "details"}',
        }
        for old, new in replacements.items():
            after = after.replace(old, new)

        if "function handleTabClick()" in after:
            after = _replace_function_body(after, "handleTabClick", "  function handleTabClick() {\n    setActiveTab('details');\n  }")

        return _write_if_changed(target, before, after, "Wired tab buttons to React state and conditional panels.")


def _find_form_file(workspace_path: Path) -> Path | None:
    preferred = workspace_path / "src" / "components" / "ContactForm.jsx"
    if preferred.exists():
        return preferred
    for path in sorted((workspace_path / "src").rglob("*.jsx")):
        if "<form" in path.read_text(encoding="utf-8"):
            return path
    return None


def _find_nav_file(workspace_path: Path) -> Path | None:
    for path in sorted((workspace_path / "src").rglob("*.jsx")):
        source = path.read_text(encoding="utf-8")
        if "nav-menu" in source and "handleMenuClick" in source:
            return path
    for path in sorted((workspace_path / "src").rglob("*.jsx")):
        source = path.read_text(encoding="utf-8")
        if "<nav" in source and "Menu" in source:
            return path
    return None


def _find_tabs_file(workspace_path: Path) -> Path | None:
    for path in sorted((workspace_path / "src").rglob("*.jsx")):
        source = path.read_text(encoding="utf-8")
        if "tab-panel" in source and ("role=\"tab\"" in source or "data-tab" in source):
            return path
    return None


def _normalize_failure_types(failure_types: list[str]) -> list[str]:
    normalized: list[str] = []
    for failure_type in failure_types:
        if failure_type == "missing_submit_feedback" and "submit_button_no_handler" in failure_types:
            continue
        if failure_type not in normalized:
            normalized.append(failure_type)
    return normalized


def _insert_after_function_open(source: str, insertion: str) -> str:
    markers = ["export function ContactForm() {", "export default function App() {", "function App() {"]
    for marker in markers:
        if marker in source:
            return source.replace(marker, marker + "\n" + insertion, 1)
    return source


def _insert_before_first_form_button(source: str, insertion: str) -> str:
    form_start = source.find("<form")
    form_end = source.find("</form>", form_start)
    if form_start == -1 or form_end == -1:
        return source

    form_source = source[form_start:form_end]
    button_index = form_source.find("<button")
    if button_index != -1:
        absolute_button_index = form_start + button_index
        insert_at = _line_start_before(source, absolute_button_index)
        indent = _line_indent_before(source, absolute_button_index)
        return source[:insert_at] + _indent_block(insertion, indent) + "\n" + source[insert_at:]
    indent = _line_indent_before(source, form_end) + "  "
    insert_at = _line_start_before(source, form_end)
    return source[:insert_at] + _indent_block(insertion, indent) + "\n" + source[insert_at:]


def _insert_before_first_form_close(source: str, insertion: str) -> str:
    form_start = source.find("<form")
    form_end = source.find("</form>", form_start)
    if form_start == -1 or form_end == -1:
        return source
    indent = _line_indent_before(source, form_end) + "  "
    insert_at = _line_start_before(source, form_end)
    return source[:insert_at] + _indent_block(insertion, indent) + "\n" + source[insert_at:]


def _line_start_before(source: str, index: int) -> int:
    return source.rfind("\n", 0, index) + 1


def _line_indent_before(source: str, index: int) -> str:
    line_start = _line_start_before(source, index)
    return source[line_start:index]


def _indent_block(block: str, indent: str) -> str:
    return "\n".join(indent + line if line else line for line in block.splitlines())


def _replace_function_body(source: str, function_name: str, replacement: str) -> str:
    marker = f"function {function_name}() {{"
    marker_start = source.find(marker)
    if marker_start == -1:
        return source
    start = marker_start
    line_start = source.rfind("\n", 0, marker_start) + 1
    leading = source[line_start:marker_start]
    if leading.strip() == "":
        start = line_start
        replacement = replacement + "\n"
    index = marker_start + len(marker)
    depth = 1
    while index < len(source):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[:start] + replacement + source[index + 1 :]
        index += 1
    return source


def _write_if_changed(target: Path, before: str, after: str, detail: str) -> tuple[bool, list[str], list[str], dict[str, str]]:
    if before == after:
        return False, [], [f"No changes needed in {target.name}."], {}
    target.write_text(after, encoding="utf-8")
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{target.name}",
            tofile=f"b/{target.name}",
        )
    )
    return True, [str(target)], [detail], {str(target): diff}


def _uses_llm(provider: LLMProvider) -> bool:
    return getattr(provider, "provider_name", "mock") != "mock"


def _record_provider_fallback(provider: LLMProvider, reason: str) -> None:
    record = getattr(provider, "record_fallback", None)
    if callable(record):
        record(reason)


def _snapshot_workspace_files(workspace_path: Path) -> dict[str, str]:
    ignored_parts = {"node_modules", "dist", "build", ".git"}
    snapshots: dict[str, str] = {}
    for path in sorted(workspace_path.rglob("*")):
        if not path.is_file():
            continue
        relative_path = str(path.relative_to(workspace_path))
        if ignored_parts.intersection(Path(relative_path).parts):
            continue
        if not relative_path.endswith((".jsx", ".js", ".css", ".html", ".json")):
            continue
        content = path.read_text(encoding="utf-8")
        if len(content) <= 40_000:
            snapshots[relative_path] = content
    return snapshots


def _diff_touched_files(workspace_path: Path, before: dict[str, str], files_touched: list[str]) -> dict[str, str]:
    diffs: dict[str, str] = {}
    for relative_path in files_touched:
        target = workspace_path / relative_path
        if not target.exists():
            continue
        before_text = before.get(relative_path, "")
        after_text = target.read_text(encoding="utf-8")
        if before_text == after_text:
            continue
        from_file = f"a/{relative_path}" if relative_path in before else "/dev/null"
        diffs[relative_path] = "".join(
            difflib.unified_diff(
                before_text.splitlines(keepends=True),
                after_text.splitlines(keepends=True),
                fromfile=from_file,
                tofile=f"b/{relative_path}",
            )
        )
    return diffs


def _safe_workspace_path(workspace_path: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe LLM repair path: {relative_path}")
    target = (workspace_path / path).resolve()
    workspace = workspace_path.resolve()
    if workspace not in target.parents and target != workspace:
        raise ValueError(f"Unsafe LLM repair path outside workspace: {relative_path}")
    if any(part in {"node_modules", "dist", "build", ".git"} for part in path.parts):
        raise ValueError(f"Unsafe generated artifact path: {relative_path}")
    return target


def _repair_prompt(
    task: Task,
    reflection: dict[str, Any],
    files: dict[str, str],
    artifact_paths: dict[str, Any],
) -> str:
    return f"""Repair this WebPilot workspace using the smallest safe full-file replacements.

Return strict JSON only with this schema:
{{
  "files": [
    {{"path": "relative/path.ext", "content": "complete replacement file content"}}
  ],
  "reasoning": "brief explanation"
}}

Rules:
- Return only files that must be modified or added.
- Do not touch node_modules, dist, build, package-lock files, or unrelated files.
- Preserve the Vite/React project structure.
- Prefer targeted edits that address the reflection.

Task:
{json.dumps(task.to_dict(), indent=2)}

Reflection:
{json.dumps(reflection, indent=2)}

Artifact paths:
{json.dumps(artifact_paths, indent=2)}

Current workspace files:
{json.dumps(files, indent=2)}
"""


def _parse_repair_files(raw: str) -> dict[str, str]:
    data = json.loads(_strip_json_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("repair output must be a JSON object")
    raw_files = data.get("files")
    files: dict[str, str] = {}
    if isinstance(raw_files, dict):
        iterator = raw_files.items()
    elif isinstance(raw_files, list):
        iterator = []
        for item in raw_files:
            if not isinstance(item, dict):
                raise ValueError("repair files list items must be objects")
            iterator.append((item.get("path"), item.get("content")))
    else:
        raise ValueError("repair output must include files")

    for relative_path, content in iterator:
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("repair file path must be a non-empty string")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"repair content for {relative_path} must be non-empty")
        if len(content) > 100_000:
            raise ValueError(f"repair content for {relative_path} is too large")
        files[relative_path] = content
    if len(files) > 16:
        raise ValueError("LLM repair returned too many files")
    return files


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
