"""Deterministic template-based repairs for known WebPilot MVP failures."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any


class Repairer:
    """Applies localized file edits for known browser-feedback failure types."""

    def repair(self, reflection: dict[str, Any], workspace_path: Path) -> dict[str, Any]:
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
            else:
                plan["skipped_repair_types"].append(failure_type)
                plan["details"].append(f"No automated repair available for {failure_type}.")

        return plan

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
            inserts.append('        <label>\n          Name\n          <input name="name" type="text" placeholder="Alex Morgan" autoComplete="name" />\n        </label>')
        if 'name="email"' not in lower and 'type="email"' not in lower:
            inserts.append('        <label>\n          Email\n          <input name="email" type="email" placeholder="alex@example.com" autoComplete="email" />\n        </label>')
        if 'name="message"' not in lower:
            inserts.append('        <label>\n          Message\n          <textarea name="message" placeholder="How can we help?" rows="5" />\n        </label>')

        if inserts:
            after = _insert_inside_first_form(after, "\n".join(inserts))

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
            after = after.replace("</form>", "        {submitted && <p role=\"status\" className=\"form-status\">Message sent</p>}\n        </form>", 1)

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


def _insert_inside_first_form(source: str, insertion: str) -> str:
    form_start = source.find("<form")
    form_end = source.find("</form>", form_start)
    if form_start == -1 or form_end == -1:
        return source

    form_source = source[form_start:form_end]
    button_index = form_source.find("<button")
    if button_index != -1:
        absolute_button_index = form_start + button_index
        return source[:absolute_button_index] + insertion + "\n" + source[absolute_button_index:]
    return source[:form_end] + insertion + "\n" + source[form_end:]


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
