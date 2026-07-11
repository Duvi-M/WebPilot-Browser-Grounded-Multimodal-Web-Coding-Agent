# WebPilot Evaluation Report

## 1. Setup

This report evaluates the current WebPilot MVP on 9 deterministic tasks across 3 task types: `text_generation` (`task_001`, `task_003`, `task_007`), `diagnostic_repair` (`task_002`, `task_004`, `task_008`), and `editing` (`task_005`, `task_006`, `task_009`). Each task was run with 2 variants: `base` with `max_iterations=1`, and `browser-feedback` with `max_iterations=3`.

The consolidated runs used as the data source are:

- Base: `runs/evaluation/20260711T074701Z/evaluation_summary.json`
- Browser feedback: `runs/evaluation/20260711T074747Z/evaluation_summary.json`

The mock LLM provider was used throughout these evaluation runs. The OpenAI provider exists and is covered by unit tests, but it was not evaluated here with a real API key, so these results do not measure real OpenAI-backed planning, generation, or repair behavior.

`patch_quality` is a heuristic for `diagnostic_repair` and `editing` tasks. Editing runs write `iteration_0/edit_plan.json` with unified diffs, so edit size is scored from changed diff lines instead of a touched-file proxy. It is still `None` for `text_generation`, because generation has no patch relative to an existing repository.

`visual_quality` remains the paper-aligned placeholder for future multimodal LLM-as-a-judge scoring and currently returns `None`. `visual_sanity_score` is a separate non-LLM smoke heuristic based only on already collected browser evidence: page loaded, DOM is not blank, and mobile overflow passes when that signal exists. It is useful for catching obvious broken render states, but it is not a substitute for visual coherence or instruction-alignment judging.

## 2. Ablation Table

| task_id | type | variant | executability | interaction_correctness | patch_quality | visual_sanity_score | visual_quality | iterations | final_status | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| task_007 | text_generation | base | passed | 1.00 | None | 1.0000 | None | 1 | passed | `runs/task_007/20260711T074701Z/summary.json` |
| task_003 | text_generation | base | passed | 1.00 | None | 1.0000 | None | 1 | passed | `runs/task_003/20260711T074706Z/summary.json` |
| task_002 | diagnostic_repair | base | passed | 0.62 | 0.6054 | 0.6667 | None | 1 | failed | `runs/task_002/20260711T074710Z/summary.json` |
| task_006 | editing | base | passed | 1.00 | 0.6725 | 1.0000 | None | 1 | passed | `runs/task_006/20260711T074715Z/summary.json` |
| task_009 | editing | base | passed | 1.00 | 0.8482 | 1.0000 | None | 1 | passed | `runs/task_009/20260711T074719Z/summary.json` |
| task_005 | editing | base | passed | 1.00 | 0.6950 | 1.0000 | None | 1 | passed | `runs/task_005/20260711T074723Z/summary.json` |
| task_004 | diagnostic_repair | base | passed | 0.83 | 0.6054 | 1.0000 | None | 1 | failed | `runs/task_004/20260711T074730Z/summary.json` |
| task_008 | diagnostic_repair | base | passed | 0.83 | 0.6054 | 1.0000 | None | 1 | failed | `runs/task_008/20260711T074734Z/summary.json` |
| task_001 | text_generation | base | passed | 0.88 | None | 1.0000 | None | 1 | failed | `runs/task_001/20260711T074738Z/summary.json` |
| task_007 | text_generation | browser-feedback | passed | 1.00 | None | 1.0000 | None | 1 | passed | `runs/task_007/20260711T074747Z/summary.json` |
| task_003 | text_generation | browser-feedback | passed | 1.00 | None | 1.0000 | None | 1 | passed | `runs/task_003/20260711T074752Z/summary.json` |
| task_002 | diagnostic_repair | browser-feedback | passed | 1.00 | 0.8107 | 1.0000 | None | 2 | passed | `runs/task_002/20260711T074756Z/summary.json` |
| task_006 | editing | browser-feedback | passed | 1.00 | 0.6725 | 1.0000 | None | 1 | passed | `runs/task_006/20260711T074804Z/summary.json` |
| task_009 | editing | browser-feedback | passed | 1.00 | 0.8482 | 1.0000 | None | 1 | passed | `runs/task_009/20260711T074809Z/summary.json` |
| task_005 | editing | browser-feedback | passed | 1.00 | 0.6950 | 1.0000 | None | 1 | passed | `runs/task_005/20260711T074814Z/summary.json` |
| task_004 | diagnostic_repair | browser-feedback | passed | 1.00 | 0.9179 | 1.0000 | None | 2 | passed | `runs/task_004/20260711T074817Z/summary.json` |
| task_008 | diagnostic_repair | browser-feedback | passed | 1.00 | 0.9079 | 1.0000 | None | 2 | passed | `runs/task_008/20260711T074824Z/summary.json` |
| task_001 | text_generation | browser-feedback | passed | 1.00 | None | 1.0000 | None | 2 | passed | `runs/task_001/20260711T074831Z/summary.json` |

Browser feedback improved interaction correctness on 4 of 9 tasks: `task_001`, `task_002`, `task_004`, and `task_008`. The new blog layout task (`task_007`) passes in both variants. The new secondary CTA editing task (`task_009`) also passes in both variants with a small patch. The new tabs repair task (`task_008`) fails in base and passes after browser-feedback applies a deterministic state-wiring repair.

## 3. Case Studies

### A. New Repair Pattern: Tab Switcher State

`task_008` starts from `webpilot/examples/buggy_tabs_app`, where clicking the Details tab does not change the visible panel. In the base run, the app loads but fails the tab interaction check. Source: `runs/task_008/20260711T074734Z/iteration_0/test_results.json`.

```json
{
  "check_name": "tabs_switch_content",
  "details": "Clicking the second tab did not change visible panel content.",
  "passed": false
}
```

The browser-feedback run maps that failure to `tabs_no_state_switch` and applies a deterministic repair. Source: `runs/task_008/20260711T074824Z/iteration_0/repair_plan.json`.

```json
{
  "repairs_applied": ["tabs_no_state_switch"]
}
```

The diff adds React state, wires both tab buttons, and makes each panel conditional:

```diff
+import { useState } from 'react';
 export default function App() {
+  const [activeTab, setActiveTab] = useState('overview');
...
-          <button type="button" role="tab" aria-selected="false" onClick={handleTabClick}>
+          <button type="button" role="tab" aria-selected={activeTab === "details"} onClick={() => setActiveTab("details")}>
...
-        <section className="tab-panel" role="tabpanel" hidden>
+        <section className={activeTab === "details" ? "tab-panel panel-active" : "tab-panel"} role="tabpanel" hidden={activeTab !== "details"}>
```

The next iteration passes with `interaction_correctness=1.00`, `patch_quality=0.9079`, and `visual_sanity_score=1.0000`.

### B. Browser Feedback Fixed a Form/Overflow Defect

`task_002` starts from a deliberately broken app. In the base run, it rendered but failed multiple interaction checks. Source: `runs/task_002/20260711T074710Z/iteration_0/test_results.json`.

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

The browser-feedback run repaired missing form fields, submit feedback, and horizontal overflow. The next iteration passed with `interaction_correctness=1.00`. Source: `runs/task_002/20260711T074756Z/summary.json`.

### C. New Generation Pattern: Blog Article With Related Posts

`task_007` exercises a layout that is not a landing page or dashboard. The generated workspace includes `ArticleLayout.jsx` and `RelatedPosts.jsx`. Source: `runs/task_007/20260711T074747Z/generated_workspace/src/App.jsx`.

```jsx
import { ArticleLayout } from './components/ArticleLayout.jsx';
import { RelatedPosts } from './components/RelatedPosts.jsx';

export default function App() {
  return (
    <main className="app blog-layout">
      <ArticleLayout />
      <RelatedPosts />
    </main>
  );
}
```

The browser run passes the article/sidebar content check, generic button checks, and mobile overflow check in 1 iteration.

### D. New Editing Pattern: Secondary CTA

`task_009` adds a secondary CTA button to the existing editable landing fixture. Source: `runs/task_009/20260711T074809Z/iteration_0/edit_plan.json`.

```diff
         <a className="cta-button" href="#contact">Talk to us</a>
+        <a className="secondary-cta-button" href="#pricing">View case studies</a>
```

The edit also appends CSS for `.secondary-cta-button`. The diff has 15 changed lines across 2 files, and `patch_quality` is `0.8482`.

## 4. Known Limitations

- The deterministic repairer now covers missing form fields, submit feedback/handlers, mobile overflow, simple nav state toggles, and a simple tab-switcher state repair. It still does not handle complex modals, dropdown filtering, routing, focus traps, async UI, or arbitrary React state bugs.
- The interaction tester now includes tab switching detection, but it is still a deterministic check rather than generated test synthesis.
- Dashboard generation covers sidebar navigation, summary stats, and a static data table. It does not support sorting, filtering, pagination, charts, or live data.
- Blog generation covers a static article plus related-posts sidebar. It is not a general article/page-layout generator.
- Editing now covers testimonials, FAQ, simple CTA insertion/update, newsletter signup, and secondary CTA insertion. It is still pattern-based, not general-purpose repository editing.
- Mock-mode planning and coding remain keyword-based.
- The OpenAI provider is implemented and unit-tested, but these evaluation runs did not use a real `OPENAI_API_KEY`.
- `patch_quality` and `visual_sanity_score` are heuristics. They are not human or LLM judgments.
- `visual_quality` is still a placeholder and returns `None` until a real multimodal judge is available.
- The evaluation has only 9 tasks total, much smaller than the paper-scale target set.
- No vision-guided or multimodal input is evaluated yet.

## 5. Next Steps Suggested by These Runs

The most useful deterministic coverage gaps left are modal open/close repair, dropdown filter repair, and richer dashboard interactions such as sorting/filtering. After those fixtures exist, the next high-leverage research step is enabling real LLM-backed planning/generation/repair with an API key and comparing it against the deterministic mock baseline.
