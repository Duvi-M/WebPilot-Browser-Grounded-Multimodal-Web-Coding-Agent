# WebPilot Evaluation Report

## 1. Setup

This report evaluates the deterministic/mock WebPilot MVP on 9 local tasks:

- `text_generation`: `task_001`, `task_003`, `task_007`
- `diagnostic_repair`: `task_002`, `task_004`, `task_008`
- `editing`: `task_005`, `task_006`, `task_009`

Fresh evaluation runs from 2026-07-16:

- Base: `runs/evaluation/20260716T080657Z/evaluation_summary.json`
- Browser feedback: `runs/evaluation/20260716T080545Z/evaluation_summary.json`

The mock provider was used throughout. No OpenAI API calls were made for these results.

`patch_quality` is a heuristic for repair/editing tasks. `visual_sanity_score` is a browser-evidence smoke heuristic. `visual_quality` is still the paper-aligned placeholder for future multimodal judging and currently returns `None`.

## 2. Latest Base Result for `task_001`

The generated `ContactForm` now includes React state, `event.preventDefault()`, `onSubmit={handleSubmit}`, visible `Message sent` feedback, and labeled name/email/message fields.

Fresh base run:

- Summary: `runs/task_001/20260716T080450Z/summary.json`
- `final_status`: `passed`
- `interaction_correctness_score`: `1.0`
- `iterations`: `1`
- `repairs_attempted`: `[]`
- No `repair_plan.json` was generated in base mode.

This fixes the audit finding where `sample_text_generation` previously failed in base mode due to missing submit feedback.

## 3. Ablation Summary

| variant | tasks | passed | failed | notes |
|---|---:|---:|---:|---|
| `base` | 9 | 6 | 3 | Generation and editing samples pass; diagnostic repair tasks still fail because base mode does not repair. |
| `browser-feedback` | 9 | 9 | 0 | All tasks pass; diagnostic repair tasks require 2 iterations, while normal generation/editing tasks pass in 1. |

Browser feedback improves the three diagnostic repair tasks:

- `task_002`: form field, submit feedback, and mobile overflow repair.
- `task_004`: nav menu state-toggle repair.
- `task_008`: tab switcher state repair.

After the ContactForm fix, `task_001` no longer needs browser-feedback repair. In the fresh browser-feedback evaluation it passes in 1 iteration.

## 4. Base Evaluation Table

| task_id | type | executability | interaction_correctness | patch_quality | visual_sanity_score | visual_quality | iterations | final_status |
|---|---|---|---:|---:|---:|---|---:|---|
| `task_007` | text_generation | passed | 1.00 | None | 1.0000 | None | 1 | passed |
| `task_003` | text_generation | passed | 1.00 | None | 1.0000 | None | 1 | passed |
| `task_002` | diagnostic_repair | passed | 0.62 | 0.6054 | 0.6667 | None | 1 | failed |
| `task_006` | editing | passed | 1.00 | 0.6725 | 1.0000 | None | 1 | passed |
| `task_009` | editing | passed | 1.00 | 0.8482 | 1.0000 | None | 1 | passed |
| `task_005` | editing | passed | 1.00 | 0.6950 | 1.0000 | None | 1 | passed |
| `task_004` | diagnostic_repair | passed | 0.83 | 0.6054 | 1.0000 | None | 1 | failed |
| `task_008` | diagnostic_repair | passed | 0.83 | 0.6054 | 1.0000 | None | 1 | failed |
| `task_001` | text_generation | passed | 1.00 | None | 1.0000 | None | 1 | passed |

## 5. Browser-Feedback Evaluation Table

| task_id | type | executability | interaction_correctness | patch_quality | visual_sanity_score | visual_quality | iterations | final_status |
|---|---|---|---:|---:|---:|---|---:|---|
| `task_007` | text_generation | passed | 1.00 | None | 1.0000 | None | 1 | passed |
| `task_003` | text_generation | passed | 1.00 | None | 1.0000 | None | 1 | passed |
| `task_002` | diagnostic_repair | passed | 1.00 | 0.8107 | 1.0000 | None | 2 | passed |
| `task_006` | editing | passed | 1.00 | 0.6725 | 1.0000 | None | 1 | passed |
| `task_009` | editing | passed | 1.00 | 0.8482 | 1.0000 | None | 1 | passed |
| `task_005` | editing | passed | 1.00 | 0.6950 | 1.0000 | None | 1 | passed |
| `task_004` | diagnostic_repair | passed | 1.00 | 0.9179 | 1.0000 | None | 2 | passed |
| `task_008` | diagnostic_repair | passed | 1.00 | 0.9079 | 1.0000 | None | 2 | passed |
| `task_001` | text_generation | passed | 1.00 | None | 1.0000 | None | 1 | passed |

## 6. Case Studies

### A. Generation Robustness: Contact Form Feedback

`task_001` now passes in base mode. The generated `src/components/ContactForm.jsx` includes `useState`, an `onSubmit` handler, `event.preventDefault()`, and visible `Message sent` feedback with `role="status"`.

This matters because simple text generation should not depend on the repair loop for basic form behavior.

### B. Diagnostic Repair: Form and Overflow

`task_002` still validates the repair loop. Iteration 0 detects:

- Missing `message` field.
- Missing submit feedback.
- Mobile horizontal overflow.

The repair plan modifies `src/App.jsx` and `src/App.css`, then iteration 1 passes with `interaction_correctness_score: 1.0`.

Fresh diagnostic repair run:

- Summary: `runs/task_002/20260716T080515Z/summary.json`
- Repair plan: `runs/task_002/20260716T080515Z/iteration_0/repair_plan.json`

### C. Navigation and Tabs

`task_004` and `task_008` fail in base mode and pass in browser-feedback mode after deterministic state repairs. These remain useful examples of the `execute -> inspect -> repair -> re-execute` loop.

## 7. Known Limitations

- This is still a deterministic/mock MVP, not a full WebCompass or multimodal evaluation.
- The mock planner and coder are keyword/template based.
- The repairer covers fixed patterns only: form fields, submit feedback, mobile overflow, nav menu state, and tab switcher state.
- The interaction tester is deterministic; there is no test-synthesis variant yet.
- There is no visual-reflection variant yet.
- Vision-guided generation and editing are not implemented.
- The OpenAI provider exists and is unit-tested, but it was not used in these evaluation runs.
- `patch_quality` and `visual_sanity_score` are heuristic proxies, not human or LLM judgments.
- `visual_quality` remains `None` until a real multimodal judge or comparison rubric is added.
- The task set is only 9 local tasks, so the results are smoke/MVP evidence rather than paper-scale benchmark evidence.

## 8. Next Steps

1. Keep the current deterministic MVP green.
2. Add a few more local repair fixtures before introducing LLM variability.
3. Add bounded OpenAI-provider evaluation only after prompt logging and budget controls are in place.
4. Add vision/WebCompass/test-synthesis/visual-reflection later as separate milestones.
