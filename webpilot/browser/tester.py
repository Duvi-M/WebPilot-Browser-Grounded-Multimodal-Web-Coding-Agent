"""Playwright-driven interaction checks for WebPilot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from webpilot.task_schema import Task


@dataclass(frozen=True)
class TestResult:
    check_name: str
    passed: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {"check_name": self.check_name, "passed": self.passed, "details": self.details}


class InteractionTester:
    """Runs deterministic checks without aborting the whole iteration on failures."""

    def run(self, page: Any, task: Task) -> list[TestResult]:
        results: list[TestResult] = []
        results.append(self._safe("page_loaded", lambda: self._page_loaded(page)))
        results.append(self._safe("expected_sections_visible", lambda: self._expected_sections(page, task)))
        results.append(self._safe("buttons_exist", lambda: self._buttons_exist(page)))
        results.append(self._safe("buttons_clickable_no_page_error", lambda: self._buttons_clickable(page)))
        results.append(self._safe("form_has_name_email_message", lambda: self._form_fields(page)))
        results.append(self._safe("cta_click_does_not_crash", lambda: self._cta_click(page)))
        results.append(self._safe("submit_shows_feedback", lambda: self._submit_feedback(page)))
        results.append(self._safe("mobile_has_no_horizontal_overflow", lambda: self._mobile_overflow(page)))
        return results

    def _safe(self, check_name: str, check: Any) -> TestResult:
        try:
            return check()
        except Exception as exc:  # Playwright errors should become check failures, not run crashes.
            return TestResult(check_name=check_name, passed=False, details=f"{type(exc).__name__}: {exc}")

    def _page_loaded(self, page: Any) -> TestResult:
        body = page.locator("body")
        body.wait_for(state="visible", timeout=3000)
        return TestResult("page_loaded", True, "The document body is visible.")

    def _expected_sections(self, page: Any, task: Task) -> TestResult:
        source = " ".join([task.instruction, *task.expected_behaviors, *task.test_hints]).lower()
        missing: list[str] = []
        checks = {
            "hero": "text=/hero|manage|task management|generated/i",
            "pricing": "text=/pricing|starter|pro|team/i",
            "contact": "text=/contact|email|message/i",
        }
        for name, selector in checks.items():
            if name in source and page.locator(selector).count() == 0:
                missing.append(name)
        if missing:
            return TestResult("expected_sections_visible", False, f"Missing expected sections/text: {', '.join(missing)}.")
        return TestResult("expected_sections_visible", True, "Expected visible sections/text were found.")

    def _buttons_exist(self, page: Any) -> TestResult:
        count = page.locator("button, a.cta-button, [role=button]").count()
        return TestResult("buttons_exist", count > 0, f"Found {count} button-like elements.")

    def _buttons_clickable(self, page: Any) -> TestResult:
        before_errors = len(page.context._webpilot_page_errors) if hasattr(page.context, "_webpilot_page_errors") else 0
        buttons = page.locator("button, a.cta-button, [role=button]")
        count = min(buttons.count(), 3)
        for index in range(count):
            buttons.nth(index).click(timeout=1500, trial=True)
        after_errors = len(page.context._webpilot_page_errors) if hasattr(page.context, "_webpilot_page_errors") else before_errors
        passed = after_errors == before_errors
        return TestResult("buttons_clickable_no_page_error", passed, f"Trial-clicked {count} button-like elements.")

    def _form_fields(self, page: Any) -> TestResult:
        selectors = {
            "name": 'input[name="name"], input[autocomplete="name"], input[placeholder*="name" i]',
            "email": 'input[name="email"], input[type="email"], input[autocomplete="email"]',
            "message": 'textarea[name="message"], textarea[placeholder*="message" i], input[name="message"]',
        }
        missing = [name for name, selector in selectors.items() if page.locator(selector).count() == 0]
        if missing:
            return TestResult("form_has_name_email_message", False, f"Missing fields: {', '.join(missing)}.")
        return TestResult("form_has_name_email_message", True, "Found name, email, and message fields.")

    def _cta_click(self, page: Any) -> TestResult:
        before_errors = len(page.context._webpilot_page_errors) if hasattr(page.context, "_webpilot_page_errors") else 0
        cta = page.locator('a.cta-button, button:has-text("Start"), button:has-text("Choose")').first
        if cta.count() == 0:
            return TestResult("cta_click_does_not_crash", False, "No CTA element found.")
        cta.click(timeout=2000)
        page.wait_for_timeout(250)
        after_errors = len(page.context._webpilot_page_errors) if hasattr(page.context, "_webpilot_page_errors") else before_errors
        return TestResult("cta_click_does_not_crash", after_errors == before_errors, "Clicked the first CTA without new page errors.")

    def _submit_feedback(self, page: Any) -> TestResult:
        form = page.locator("form").first
        if form.count() == 0:
            return TestResult("submit_shows_feedback", False, "No form found.")

        self._fill_if_present(page, 'input[name="name"], input[autocomplete="name"]', "Alex Morgan")
        self._fill_if_present(page, 'input[name="email"], input[type="email"]', "alex@example.com")
        self._fill_if_present(page, 'textarea[name="message"], input[name="message"]', "Please help our team plan better.")

        before_text = page.locator("body").inner_text(timeout=2000)
        submit = form.locator('button[type="submit"], button').first
        if submit.count() == 0:
            return TestResult("submit_shows_feedback", False, "No submit button found.")
        submit.click(timeout=2000)
        page.wait_for_timeout(500)
        after_text = page.locator("body").inner_text(timeout=2000)
        markers = ["sent", "submitted", "thank", "message sent"]
        visible_marker = any(marker in after_text.lower() for marker in markers)
        text_changed = after_text != before_text
        passed = visible_marker or text_changed
        details = "Submit produced visible feedback." if passed else "Submit did not produce visible confirmation text."
        return TestResult("submit_shows_feedback", passed, details)

    def _mobile_overflow(self, page: Any) -> TestResult:
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(250)
        sizes = page.evaluate(
            "() => ({ scrollWidth: document.documentElement.scrollWidth, width: window.innerWidth })"
        )
        overflow = int(sizes["scrollWidth"]) - int(sizes["width"])
        passed = overflow <= 4
        return TestResult(
            "mobile_has_no_horizontal_overflow",
            passed,
            f"scrollWidth={sizes['scrollWidth']}, viewportWidth={sizes['width']}.",
        )

    def _fill_if_present(self, page: Any, selector: str, value: str) -> None:
        locator = page.locator(selector).first
        if locator.count() > 0:
            locator.fill(value, timeout=1500)

