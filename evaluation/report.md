# WebPilot Evaluation Report

## 1. Setup

This report evaluates the current WebPilot MVP on 6 tasks across 3 task types: `text_generation` (`task_001`, `task_003`), `diagnostic_repair` (`task_002`, `task_004`), and `editing` (`task_005`, `task_006`). Each task was run with 2 variants: `base` with `max_iterations=1`, and `browser-feedback` with `max_iterations=3`.

The consolidated runs used as the data source are:

- Base: `runs/evaluation/20260710T210728Z/evaluation_summary.json`
- Browser feedback: `runs/evaluation/20260710T210638Z/evaluation_summary.json`

The mock LLM provider was used throughout these evaluation runs. The OpenAI provider exists and is covered by unit tests, but it was not evaluated here with a real API key, so these results do not measure real OpenAI-backed planning, generation, or repair behavior.

`patch_quality` is now a real heuristic for `diagnostic_repair` and `editing` tasks. Editing runs write `iteration_0/edit_plan.json` with unified diffs, so edit size is scored from changed diff lines instead of a touched-file proxy. It is still `None` for `text_generation`, because generation has no patch relative to an existing repository. `visual_quality` remains a placeholder and currently returns `None`.

## 2. Ablation Table

| task_id | type | variant | executability | interaction_correctness | patch_quality | iterations | final_status | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| task_003 | text_generation | base | passed | 1.0 | None | 1 | passed | `runs/task_003/20260710T210728Z/summary.json` |
| task_002 | diagnostic_repair | base | passed | 0.625 | 0.6054 | 1 | failed | `runs/task_002/20260710T210735Z/summary.json` |
| task_006 | editing | base | passed | 1.0 | 0.6725 | 1 | passed | `runs/task_006/20260710T210740Z/summary.json` |
| task_005 | editing | base | passed | 1.0 | 0.695 | 1 | passed | `runs/task_005/20260710T210744Z/summary.json` |
| task_004 | diagnostic_repair | base | passed | 0.8333333333333334 | 0.6054 | 1 | failed | `runs/task_004/20260710T210748Z/summary.json` |
| task_001 | text_generation | base | passed | 0.875 | None | 1 | failed | `runs/task_001/20260710T210752Z/summary.json` |
| task_003 | text_generation | browser-feedback | passed | 1.0 | None | 1 | passed | `runs/task_003/20260710T210638Z/summary.json` |
| task_002 | diagnostic_repair | browser-feedback | passed | 1.0 | 0.8107 | 2 | passed | `runs/task_002/20260710T210642Z/summary.json` |
| task_006 | editing | browser-feedback | passed | 1.0 | 0.6725 | 1 | passed | `runs/task_006/20260710T210650Z/summary.json` |
| task_005 | editing | browser-feedback | passed | 1.0 | 0.695 | 1 | passed | `runs/task_005/20260710T210655Z/summary.json` |
| task_004 | diagnostic_repair | browser-feedback | passed | 1.0 | 0.9179 | 2 | passed | `runs/task_004/20260710T210659Z/summary.json` |
| task_001 | text_generation | browser-feedback | passed | 1.0 | None | 2 | passed | `runs/task_001/20260710T210706Z/summary.json` |

Browser feedback improved interaction correctness on 3 of 6 tasks: `task_001` improved from `0.875` to `1.0`, `task_002` improved from `0.625` to `1.0`, and `task_004` improved from `0.8333333333333334` to `1.0`. The dashboard task (`task_003`) now passes in the base variant because deterministic dashboard generation was added. Both editing tasks (`task_005`, `task_006`) already pass in base, so browser feedback does not change their scores.

## 3. Case Studies

### A. Browser Feedback Fixed a Real Defect

`task_002` starts from a deliberately broken app. In the base run, it rendered but failed three interaction checks. Source: `runs/task_002/20260710T210735Z/iteration_0/test_results.json`.

```json
{
  "check_name": "form_has_name_email_message",
  "details": "Missing fields: message.",
  "passed": false
}
```

```json
{
  "check_name": "mobile_has_no_horizontal_overflow",
  "details": "scrollWidth=956, viewportWidth=390.",
  "passed": false
}
```

The browser-feedback run repaired all three mapped failure types. Source: `runs/task_002/20260710T210642Z/iteration_0/repair_plan.json`.

```json
{
  "repairs_applied": [
    "missing_form_field",
    "submit_button_no_handler",
    "horizontal_overflow_mobile"
  ]
}
```

The next iteration passed with `interaction_correctness_score` of `1.0`. Source: `runs/task_002/20260710T210642Z/summary.json`.

### B. Interaction Testing Caught a Hidden Failure

`task_001` is a generated landing page. In the base run, it passed structural checks but failed the real submit interaction. Source: `runs/task_001/20260710T210752Z/iteration_0/test_results.json`.

```json
{
  "check_name": "form_has_name_email_message",
  "details": "Found name, email, and message fields.",
  "passed": true
}
```

```json
{
  "check_name": "submit_shows_feedback",
  "details": "Submit did not produce visible confirmation text.",
  "passed": false
}
```

The browser-feedback run added a submit handler and visible status text, then passed in 2 iterations. Source: `runs/task_001/20260710T210706Z/summary.json`.

### C. A Former Failure Case Is Now Closed

Before this hardening pass, `task_004` ended as `failed` with `no_automated_repair_available`. In the current base run it still fails the nav interaction. Source: `runs/task_004/20260710T210748Z/iteration_0/test_results.json`.

```json
{
  "check_name": "nav_menu_opens",
  "details": "Clicking the nav toggle did not reveal menu content.",
  "passed": false
}
```

The current browser-feedback run now applies a real nav repair. Source: `runs/task_004/20260710T210659Z/iteration_0/repair_plan.json`.

```json
{
  "repairs_applied": ["nav_menu_no_state_toggle"],
  "files_modified": [
    "/Users/duvi18/WebPilot-Browser-Grounded-Multimodal-Web-Coding-Agent/runs/task_004/20260710T210659Z/generated_workspace/src/App.jsx"
  ]
}
```

The diff adds state, toggles it on click, and makes the menu class conditional:

```diff
+import { useState } from 'react';
+  const [menuOpen, setMenuOpen] = useState(false);
-    // Intentional fixture bug: the click handler does not open the menu.
+    setMenuOpen((open) => !open);
-      <nav className="nav-menu" aria-label="Primary navigation">
+      <nav className={menuOpen ? "nav-menu open" : "nav-menu"} aria-label="Primary navigation" role="menu">
```

The final result is `passed`, `interaction_correctness_score` is `1.0`, and `patch_quality` is `0.9179`. Source: `runs/task_004/20260710T210659Z/summary.json`.

### D. Editing Task Working End to End

`task_005` adds testimonials below pricing. The plan targets a localized insertion. Source: `runs/task_005/20260710T210655Z/iteration_0/plan.json`.

```json
{
  "name": "TestimonialsSection",
  "kind": "edit_target",
  "details": {
    "pattern": "add_section",
    "insert_after": "pricing-section",
    "items": 2
  }
}
```

The generated component contains two real quotes. Source: `runs/task_005/20260710T210655Z/generated_workspace/src/components/TestimonialsSection.jsx`.

```jsx
const testimonials = [
  { name: 'Maya Chen', quote: 'The new planning flow helped our team ship with far fewer status meetings.' },
  { name: 'Jordan Lee', quote: 'We finally have one calm place to see priorities, pricing, and next steps.' },
];
```

This task passes in both variants with `interaction_correctness` of `1.0` and `patch_quality` of `0.695`. Its edit diff has 62 changed lines across 3 files. Source: `runs/task_005/20260710T210655Z/iteration_0/edit_plan.json`.

### E. New Editing Pattern: Newsletter Signup

`task_006` exercises a new deterministic editing pattern: adding a newsletter signup form before contact. Source: `runs/task_006/20260710T210650Z/generated_workspace/src/components/NewsletterSignup.jsx`.

```jsx
export function NewsletterSignup() {
  const [subscribed, setSubscribed] = useState(false);
  function handleSubmit(event) {
    event.preventDefault();
    setSubscribed(true);
  }
```

The component includes name, email, message, a Subscribe button, and visible confirmation text so the existing interaction checks pass. The task passes in 1 iteration with `patch_quality` of `0.6725`. Its edit diff has 71 changed lines across 3 files, so it scores lower than the smaller testimonials edit. Sources: `runs/task_006/20260710T210650Z/summary.json` and `runs/task_006/20260710T210650Z/iteration_0/edit_plan.json`.

## 4. Known Limitations

- The deterministic repairer now covers missing form fields, submit feedback/handlers, mobile overflow, and the simple nav state-toggle fixture. It still does not handle more complex nav menus with nested panels, async state, routing, focus traps, or animated disclosure state.
- Dashboard generation now covers sidebar navigation, summary stats, and a static data table with at least 3 rows. It does not support sorting, filtering, pagination, charts, or live data.
- Editing now covers testimonials, FAQ, simple CTA insertion/update, and newsletter signup. It is still pattern-based, not general-purpose repository editing.
- Mock-mode planning and coding remain keyword-based.
- The OpenAI provider is implemented and unit-tested, but these evaluation runs did not use a real `OPENAI_API_KEY`.
- `patch_quality` is a heuristic proxy based on localization, diff size, and targetedness. Editing tasks now provide real unified diffs in `edit_plan.json`; it is still not a human or LLM judgment of semantic patch quality.
- `visual_quality` is still a placeholder and returns `None`.
- The evaluation has only 6 tasks total, much smaller than the paper-scale target set.
- No vision-guided or multimodal input is evaluated yet.

## 5. Next Steps Suggested by These Runs

The current failures that were easy to close were coverage gaps in deterministic patterns: dashboard component generation and nav state repair. The next useful stress tests should target broader variants of the same categories, such as dashboards with sorting/filtering and nav menus with nested state or keyboard/focus behavior. After that, LLM-driven repair is the next high-leverage step because the deterministic repairer will keep hitting pattern coverage limits.
