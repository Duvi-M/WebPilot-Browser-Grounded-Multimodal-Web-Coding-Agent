# WebPilot Evaluation Report

## 1. Setup

This report evaluates the current WebPilot MVP on 5 tasks across 3 task types: `text_generation` (`task_001`, `task_003`), `diagnostic_repair` (`task_002`, `task_004`), and `editing` (`task_005`). Each task was run with 2 variants: `base` with `max_iterations=1`, and `browser-feedback` with `max_iterations=3`.

The consolidated runs used as the data source are:

- Base: `runs/evaluation/20260710T202119Z/evaluation_summary.json`
- Browser feedback: `runs/evaluation/20260710T202146Z/evaluation_summary.json`

The mock LLM provider was used throughout these evaluation runs. The OpenAI provider exists and is covered by unit tests, but it was not evaluated here with a real API key, so these results do not measure real LLM planning, generation, or repair behavior.

`patch_quality` and `visual_quality` are placeholder metrics in `webpilot/evaluation/metrics.py`; both currently return `None` and are not included in the summary tables.

## 2. Ablation Table

| task_id | type | variant | executability | interaction_correctness | iterations | final_status | source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| task_003 | text_generation | base | passed | 0.8333333333333334 | 1 | failed | `runs/task_003/20260710T202119Z/summary.json` |
| task_002 | diagnostic_repair | base | passed | 0.625 | 1 | failed | `runs/task_002/20260710T202124Z/summary.json` |
| task_005 | editing | base | passed | 1.0 | 1 | passed | `runs/task_005/20260710T202129Z/summary.json` |
| task_004 | diagnostic_repair | base | passed | 0.8333333333333334 | 1 | failed | `runs/task_004/20260710T202133Z/summary.json` |
| task_001 | text_generation | base | passed | 0.875 | 1 | failed | `runs/task_001/20260710T202137Z/summary.json` |
| task_003 | text_generation | browser-feedback | passed | 0.8333333333333334 | 3 | failed | `runs/task_003/20260710T202146Z/summary.json` |
| task_002 | diagnostic_repair | browser-feedback | passed | 1.0 | 2 | passed | `runs/task_002/20260710T202201Z/summary.json` |
| task_005 | editing | browser-feedback | passed | 1.0 | 1 | passed | `runs/task_005/20260710T202210Z/summary.json` |
| task_004 | diagnostic_repair | browser-feedback | passed | 0.8333333333333334 | 3 | failed | `runs/task_004/20260710T202213Z/summary.json` |
| task_001 | text_generation | browser-feedback | passed | 1.0 | 2 | passed | `runs/task_001/20260710T202223Z/summary.json` |

Browser feedback improved interaction correctness on 2 of 5 tasks: `task_001` improved from `0.875` to `1.0`, and `task_002` improved from `0.625` to `1.0`. It did not improve `task_003` or `task_004`, and `task_005` already passed in the base run. This small sample supports browser feedback for the deterministic failure patterns currently covered, but it does not support a blanket claim that browser feedback improves all task types.

## 3. Case Studies

### A. Browser Feedback Fixed a Real Defect

`task_001` compiled, rendered, and passed most checks in the base run, but failed submit feedback. Source: `runs/task_001/20260710T202137Z/iteration_0/test_results.json`.

```json
{
  "check_name": "submit_shows_feedback",
  "details": "Submit did not produce visible confirmation text.",
  "passed": false
}
```

The browser-feedback run repaired this in `runs/task_001/20260710T202223Z/iteration_0/repair_plan.json`:

```json
{
  "repairs_applied": ["submit_button_no_handler"],
  "details": ["Added submit handler and visible confirmation feedback."]
}
```

The actual diff added React state, a submit handler, and visible status text:

```diff
+import { useState } from 'react';
+  const [submitted, setSubmitted] = useState(false);
+  function handleSubmit(event) {
+    event.preventDefault();
+    setSubmitted(true);
+  }
-      <form className="contact-form">
+      <form onSubmit={handleSubmit} className="contact-form">
+              {submitted && <p role="status" className="form-status">Message sent</p>}
```

The next iteration passed the previously failing check. Source: `runs/task_001/20260710T202223Z/iteration_1/test_results.json`.

```json
{
  "check_name": "submit_shows_feedback",
  "details": "Submit produced visible feedback.",
  "passed": true
}
```

### B. Interaction Testing Caught a Hidden Failure

The same `task_001` base run shows why browser execution matters: executability was `passed`, and checks like `page_loaded`, `expected_sections_visible`, `buttons_exist`, and `form_has_name_email_message` all passed, but the form was still unusable because submitting it produced no visible feedback.

Source: `runs/task_001/20260710T202137Z/iteration_0/test_results.json`.

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

This is a concrete example of a page that renders correctly enough for structural checks but still fails an interaction-level behavior.

### C. Genuine Failure the Agent Could Not Fix

`task_004` asked WebPilot to diagnose a nav menu that does not open. Browser feedback detected the failure, but the deterministic repairer had no rule for this pattern.

Source: `runs/task_004/20260710T202213Z/iteration_0/test_results.json`.

```json
{
  "check_name": "nav_menu_opens",
  "details": "Clicking the nav toggle did not reveal menu content.",
  "passed": false
}
```

The repair plan did not modify files. Source: `runs/task_004/20260710T202213Z/iteration_0/repair_plan.json`.

```json
{
  "repairs_attempted": ["no_automated_repair_available"],
  "repairs_applied": [],
  "files_modified": []
}
```

The final summary stayed failed after 3 iterations. Source: `runs/task_004/20260710T202213Z/summary.json`.

```json
{
  "final_status": "failed",
  "interaction_correctness_score": 0.8333333333333334,
  "iterations": 3
}
```

The reason is specific: the current repairer covers only known deterministic failure labels such as missing form fields, submit feedback, submit handlers, and mobile overflow. It does not yet know how to synthesize a nav-menu state fix.

### D. Editing Task Working End to End

`task_005` is the new editing category. Its instruction was: "Add a testimonials section with 2 customer quotes below the pricing section." Source: `webpilot/tasks/sample_editing_task.json`.

The real plan from `runs/task_005/20260710T202210Z/iteration_0/plan.json` targeted a localized section insertion:

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

The generated component was written at `runs/task_005/20260710T202210Z/generated_workspace/src/components/TestimonialsSection.jsx`:

```jsx
const testimonials = [
  {
    name: 'Maya Chen',
    quote: 'The new planning flow helped our team ship with far fewer status meetings.',
  },
  {
    name: 'Jordan Lee',
    quote: 'We finally have one calm place to see priorities, pricing, and next steps.',
  },
];
```

The browser-feedback evaluation for this editing task passed in 1 iteration with `interaction_correctness` of `1.0`. Source: `runs/task_005/20260710T202210Z/summary.json`.

## 4. Known Limitations

- The repairer is deterministic/template-based. In this evaluation it fixed `submit_button_no_handler`, `missing_form_field`, and `horizontal_overflow_mobile`, but it could not fix the nav-menu failure in `task_004`.
- Mock-mode planning and coding are keyword-based. The dashboard task (`task_003`) stayed at `0.8333333333333334` interaction correctness in both variants, showing that generation coverage is still narrow.
- Editing is limited to a small deterministic pattern set: testimonials, FAQ, and simple CTA button edits. It is not general-purpose repository editing.
- The OpenAI provider is implemented and unit-tested, but these evaluation runs did not use a real `OPENAI_API_KEY`.
- `patch_quality` and `visual_quality` are placeholders and currently return `None`.
- The evaluation has only 5 tasks total, not the larger task distribution implied by the paper direction, such as approximately 20 examples per category.
- There is no vision-guided or multimodal input in the evaluated loop yet.
- Test-synthesis and visual-reflection variants are not implemented in this evaluated MVP; the two evaluated variants are only `base` and `browser-feedback`.

## 5. Next Steps Suggested by These Runs

The two clean improvements (`task_001`, `task_002`) show that browser feedback is useful when the reflector can map observed failures to a deterministic repair rule. The two clean failures (`task_003`, `task_004`) suggest that the biggest current limit is repair and generation coverage breadth, not the browser execution plumbing itself. The next highest-leverage step is LLM-driven repair for unsupported failure types, especially interaction defects like nav state, followed by broader task fixtures so the evaluation stops depending on 5 hand-sized examples.
