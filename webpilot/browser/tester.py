"""Playwright-driven interaction checks for WebPilot."""

from __future__ import annotations

import re
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
        source = _task_text(task)
        results: list[TestResult] = []
        results.append(self._safe("page_loaded", lambda: self._page_loaded(page)))
        results.append(self._safe("expected_sections_visible", lambda: self._expected_sections(page, task)))
        if _mentions(source, "dashboard", "data table", "stats"):
            results.append(self._safe("dashboard_expected_content", lambda: self._dashboard_content(page)))
        if _mentions(source, "nav menu", "navigation menu", "menu opens", "toggle"):
            results.append(self._safe("nav_menu_opens", lambda: self._nav_menu_opens(page)))
        if _mentions(source, "tab", "tabs", "tab switcher", "switch tabs"):
            results.append(self._safe("tabs_switch_content", lambda: self._tabs_switch_content(page)))
        if _mentions(source, "blog", "article", "related posts"):
            results.append(self._safe("blog_expected_content", lambda: self._blog_content(page)))
        if _mentions(source, "counter", "increment", "count increases"):
            results.append(self._safe("counter_increments", lambda: self._counter_increments(page)))
        results.append(self._safe("buttons_exist", lambda: self._buttons_exist(page)))
        results.append(self._safe("buttons_clickable_no_page_error", lambda: self._buttons_clickable(page)))
        if _mentions(source, "form", "contact", "email", "message"):
            results.append(self._safe("form_has_name_email_message", lambda: self._form_fields(page)))
        if _mentions(source, "cta", "start", "choose"):
            results.append(self._safe("cta_click_does_not_crash", lambda: self._cta_click(page)))
        if _mentions(source, "submit", "form", "message sent"):
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
            selector_found = page.locator(selector).count() > 0
            if name == "hero" and not selector_found:
                selector_found = page.locator(".hero-section").count() > 0
            if name in source and not selector_found:
                missing.append(name)
        if missing:
            return TestResult("expected_sections_visible", False, f"Missing expected sections/text: {', '.join(missing)}.")
        return TestResult("expected_sections_visible", True, "Expected visible sections/text were found.")

    def _buttons_exist(self, page: Any) -> TestResult:
        count = page.locator("button, a.cta-button, [role=button]").count()
        return TestResult("buttons_exist", count > 0, f"Found {count} button-like elements.")

    def _dashboard_content(self, page: Any) -> TestResult:
        missing: list[str] = []
        sidebar_count = page.locator("aside, nav, [aria-label]").count()
        sidebar_text_count = page.locator("text=/sidebar|overview|reports/i").count()
        if sidebar_count == 0 and sidebar_text_count == 0:
            missing.append("sidebar navigation")
        if page.locator("table").count() == 0:
            missing.append("data table")
        elif page.locator("table tbody tr, table tr").count() < 3:
            missing.append("at least 3 table rows")
        if page.locator("text=/stats|revenue|users|conversion|summary/i").count() == 0:
            missing.append("summary stats")
        if missing:
            return TestResult("dashboard_expected_content", False, f"Missing dashboard content: {', '.join(missing)}.")
        return TestResult("dashboard_expected_content", True, "Found sidebar, data table, and summary stats.")

    def _blog_content(self, page: Any) -> TestResult:
        missing: list[str] = []
        if page.locator("article, .article-layout").count() == 0:
            missing.append("article")
        if page.locator("aside, .related-posts").count() == 0:
            missing.append("related posts sidebar")
        if page.locator("text=/related posts|field notes|browser grounding|article/i").count() == 0:
            missing.append("article/related text")
        if missing:
            return TestResult("blog_expected_content", False, f"Missing blog content: {', '.join(missing)}.")
        return TestResult("blog_expected_content", True, "Found article content and related posts.")

    def _nav_menu_opens(self, page: Any) -> TestResult:
        before_text = page.locator("body").inner_text(timeout=2000)
        toggle = page.locator(
            'button:has-text("Menu"), button:has-text("Open"), button[aria-label*="menu" i], button[aria-controls]'
        ).first
        if toggle.count() == 0:
            return TestResult("nav_menu_opens", False, "No nav menu toggle button found.")
        toggle.click(timeout=2000)
        page.wait_for_timeout(300)
        after_text = page.locator("body").inner_text(timeout=2000)
        menu_visible = page.locator('[role="menu"]:visible, .menu-open:visible, .nav-menu.open:visible, nav a:visible').count() > 0
        if after_text != before_text or menu_visible:
            return TestResult("nav_menu_opens", True, "Menu content appeared after clicking the toggle.")
        return TestResult("nav_menu_opens", False, "Clicking the nav toggle did not reveal menu content.")

    def _tabs_switch_content(self, page: Any) -> TestResult:
        tabs = page.locator('[role="tab"], button[data-tab], button:has-text("Overview"), button:has-text("Details")')
        if tabs.count() < 2:
            return TestResult("tabs_switch_content", False, "Fewer than 2 tab buttons found.")
        panel = page.locator('[role="tabpanel"]:visible, .tab-panel:visible, .panel-active:visible').first
        before_text = panel.inner_text(timeout=2000) if panel.count() > 0 else page.locator("body").inner_text(timeout=2000)
        tabs.nth(1).click(timeout=2000)
        page.wait_for_timeout(300)
        panel_after = page.locator('[role="tabpanel"]:visible, .tab-panel:visible, .panel-active:visible').first
        after_text = panel_after.inner_text(timeout=2000) if panel_after.count() > 0 else page.locator("body").inner_text(timeout=2000)
        selected = tabs.nth(1).get_attribute("aria-selected")
        if after_text != before_text or selected == "true":
            return TestResult("tabs_switch_content", True, "Tab click changed visible panel content.")
        return TestResult("tabs_switch_content", False, "Clicking the second tab did not change visible panel content.")

    def _buttons_clickable(self, page: Any) -> TestResult:
        before_errors = len(page.context._webpilot_page_errors) if hasattr(page.context, "_webpilot_page_errors") else 0
        buttons = page.locator("button, a.cta-button, [role=button]")
        count = min(buttons.count(), 3)
        for index in range(count):
            buttons.nth(index).click(timeout=1500, trial=True)
        after_errors = len(page.context._webpilot_page_errors) if hasattr(page.context, "_webpilot_page_errors") else before_errors
        passed = after_errors == before_errors
        return TestResult("buttons_clickable_no_page_error", passed, f"Trial-clicked {count} button-like elements.")

    def _counter_increments(self, page: Any) -> TestResult:
        body_before = page.locator("body").inner_text(timeout=2000)
        button = page.locator('button:has-text("Increment"), button:has-text("+"), [role=button]:has-text("Increment")').first
        if button.count() == 0:
            return TestResult("counter_increments", False, "No increment button found.")
        numbers_before = [int(value) for value in re.findall(r"\b\d+\b", body_before)]
        button.click(timeout=2000)
        page.wait_for_timeout(250)
        body_after = page.locator("body").inner_text(timeout=2000)
        numbers_after = [int(value) for value in re.findall(r"\b\d+\b", body_after)]
        increased = any(after > before for before, after in zip(numbers_before, numbers_after))
        if increased or body_after != body_before and "1" in body_after:
            return TestResult("counter_increments", True, "Clicking Increment increased the visible count.")
        return TestResult("counter_increments", False, "Clicking Increment did not increase a visible numeric count.")

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


def _task_text(task: Task) -> str:
    return " ".join([task.instruction, *task.expected_behaviors, *task.test_hints]).lower()


def _mentions(source: str, *keywords: str) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", source) for keyword in keywords)
