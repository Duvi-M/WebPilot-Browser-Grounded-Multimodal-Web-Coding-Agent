# WebPilot Project Status

Audit date: 2026-07-16

## 1. Executive Summary

Current classification: **MVP partially working**.

The repository has a real browser-grounded MVP: task schema, planner, coder, browser executor, interaction tester, reflector, deterministic repairer, run logger, CLI, evaluation runner, sample tasks, fixtures, tests, and artifact logging are all present. The core `implement -> execute -> inspect -> repair` loop works for the sampled browser-feedback repair run.

It is not yet a research prototype ready for full evaluation or presentation. The implementation is mostly deterministic and pattern-based, only two variants are supported (`base`, `browser-feedback`), `visual_quality` is a placeholder, there is no WebCompass-style benchmark integration, and vision-guided inputs / interaction traces are not implemented as first-class task modalities.

Important verification finding: `task_001` fails in `base` mode because the generated contact form does not show submit feedback. The same task passes in `browser-feedback` mode after one deterministic repair iteration. This is good evidence that the feedback loop is real, but it also shows the base generated app is not fully correct.

## 2. Verified Commands

Literal `python` is not available in this shell:

| Command | Result | Relevant output |
|---|---|---|
| `python -m pytest tests/` | Failed | `zsh:1: command not found: python` |

Equivalent `python3` commands were run:

| Command | Result | Relevant output |
|---|---|---|
| `python3 -m pytest tests/` | Passed | `34 passed in 28.81s` |
| `python3 -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant base --max-iterations 1` | Passed command, task failed quality gate | Summary: `runs/task_001/20260716T075240Z/summary.json`; `final_status: failed`, interaction score `0.875` |
| `python3 -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant browser-feedback --max-iterations 3` | Passed | Summary: `runs/task_001/20260716T075252Z/summary.json`; repaired submit feedback; `final_status: passed` |
| `python3 -m webpilot.cli run --task webpilot/tasks/sample_diagnostic_repair.json --variant browser-feedback --max-iterations 3` | Passed | Summary: `runs/task_002/20260716T075307Z/summary.json`; `final_status: passed`; 2 iterations |
| `python3 -m webpilot.evaluation.runner --tasks-dir webpilot/tasks --variant base --max-iterations 1` | Passed command | Output: `runs/evaluation/20260716T075321Z`; base evaluation has 5 passed tasks and 4 failed tasks |

Playwright Chromium was available; `python -m playwright install chromium` was not needed.

## 3. Current Repository Structure

Relevant tree, excluding `.venv`, `node_modules`, `dist`, `runs`, `__pycache__`, and `.git`:

```text
webpilot/
  agent/
    coder.py
    loop.py
    planner.py
    reflector.py
    repairer.py
  browser/
    executor.py
    tester.py
  evaluation/
    metrics.py
    runner.py
  examples/
    buggy_nav_app/
    buggy_repair_app/
    buggy_tabs_app/
    editable_landing_app/
  llm/
    base.py
    mock_provider.py
    openai_provider.py
  logging_utils/
    run_logger.py
  tasks/
    sample_blog_generation.json
    sample_dashboard_generation.json
    sample_diagnostic_repair.json
    sample_editing_*.json
    sample_nav_repair.json
    sample_tabs_repair.json
    sample_text_generation.json
  cli.py
  config.py
  task_schema.py
tests/
  test_cli_smoke.py
  test_editing.py
  test_hardening.py
  test_logger.py
  test_openai_provider.py
  test_planner_coder.py
  test_task_schema.py
README.md
PROJECT_PROGRESS.md
evaluation/report.md
pyproject.toml
```

## 4. Implemented Features

| Requirement from project paper | Current status | Evidence in repo | Notes |
|---|---|---|---|
| Planner | Done | `webpilot/agent/planner.py` | Deterministic keyword planner by default; can call LLM provider for generation planning. |
| Coder | Done | `webpilot/agent/coder.py` | Generates Vite/React apps, copies repair/edit fixtures, applies deterministic edits. |
| Browser Executor | Done | `webpilot/browser/executor.py` | Runs `npm install`, starts Vite, opens Chromium, captures evidence, stops process. |
| Interaction Tester | Done | `webpilot/browser/tester.py` | Deterministic Playwright checks for load, buttons, forms, overflow, dashboard/blog/nav/tabs. |
| Reflector & Repairer | Done | `reflector.py`, `repairer.py` | Detects known failure types and repairs fixed patterns. Not general-purpose. |
| text-guided generation | Done | `sample_text_generation.json`, coder templates | Works, but base sample lacks submit feedback and fails one interaction check. |
| diagnostic repair | Done | `sample_diagnostic_repair.json`, `buggy_repair_app` | Browser-feedback run repaired missing message field, submit feedback, and mobile overflow. |
| browser execution | Done | `executor.py` | Verified with fresh CLI and tests. |
| screenshots | Done | `screenshot_desktop.png`, `screenshot_mobile.png` | Fresh artifacts valid PNGs. |
| DOM snapshots | Done | `dom_snapshot.html` | Present in each iteration. |
| console logs | Done | `console_logs.json` | Captures Vite/React console messages. |
| page errors | Done | `page_errors.json` | Present; latest audited runs had `[]`. |
| interaction tests | Done | `test_results.json`, `tester.py` | Interaction scores recorded in summary. |
| repair loop | Done | `AgentLoop.run` | Browser-feedback mode repairs then re-runs browser checks. |
| run logging | Done | `run_logger.py` | Writes plans, generated files, iteration artifacts, summary. |
| evaluation runner | Done | `evaluation/runner.py` | Batch-runs JSON tasks and writes JSON/Markdown summaries. |
| base variant | Done | CLI choices and `AgentLoop` | Executes once, no repair. |
| browser-feedback variant | Done | CLI choices and `AgentLoop` | Repairs between iterations when failures are detected. |
| test-synthesis variant | Missing | No CLI choice or module | Not implemented. |
| visual-reflection variant | Missing | No CLI choice or module | Not implemented. |
| visual quality metric | Placeholder | `visual_quality()` returns `None` | `visual_sanity_score` exists but is not the paper-level visual metric. |
| patch quality metric | Partial | `evaluation/metrics.py` | Heuristic score for editing/repair; not human/LLM judged. |
| WebCompass-style tasks | Missing | No benchmark adapter | Current tasks are local handcrafted samples. |
| vision-guided generation | Missing | Task schema has no screenshot/visual fields | Not implemented. |
| vision-guided editing | Missing | Task schema has no screenshot/visual fields | Not implemented. |
| interaction traces | Partial | Fresh interaction results are logged | No trace input modality or reusable trace format. |
| OpenAI provider | Partial | `webpilot/llm/openai_provider.py`, tests | Exists and is opt-in; not used in this audit and no credits spent. |

## 5. Artifact Audit

Latest base run audited: `runs/task_001/20260716T075240Z`.

| Artifact | Status | Notes |
|---|---|---|
| `summary.json` | Valid | Present; `final_status: failed`, `executability_status: passed`, interaction score `0.875`. |
| `iteration_0/screenshot_desktop.png` | Valid | PNG, 1440 x 1628, 331 KB. |
| `iteration_0/screenshot_mobile.png` | Valid | PNG, 390 x 2175, 165 KB. |
| `iteration_0/dom_snapshot.html` | Valid | Present, 6.9 KB. |
| `iteration_0/console_logs.json` | Valid | Present, Vite/React info/debug logs. |
| `iteration_0/page_errors.json` | Valid | Present, empty array. |
| `iteration_0/dev_server_stdout.log` | Valid | Present, 258 B. |
| `iteration_0/dev_server_stderr.log` | Valid | Present, empty. |
| `iteration_0/test_results.json` | Valid | Present; one failing check: `submit_shows_feedback`. |
| `iteration_0/reflection.json` | Valid | Present; reports failed submit feedback. |
| `iteration_0/repair_plan.json` | Not expected | Base mode does not repair. |

Latest browser-feedback repair run audited: `runs/task_002/20260716T075307Z`.

| Artifact | Status | Notes |
|---|---|---|
| `summary.json` | Valid | Present; `final_status: passed`, 2 iterations, patch quality `0.8107`. |
| `iteration_0/*` core artifacts | Valid | Includes screenshots, DOM, console/page errors, logs, tests, reflection, and `repair_plan.json`. |
| `iteration_0/repair_plan.json` | Valid | Records repairs to `src/App.jsx` and `src/App.css`. |
| `iteration_1/*` core artifacts | Valid | Includes post-repair screenshots, DOM, console/page errors, logs, tests, reflection. |
| `iteration_1/screenshot_desktop.png` | Valid | PNG, 1496 x 1143, 50 KB. |
| `iteration_1/screenshot_mobile.png` | Valid | PNG, 446 x 1279, 51 KB. |
| `iteration_1/test_results.json` | Valid | All 8 checks passed. |

## 6. Diagnostic Repair Audit

Broken fixture: `webpilot/examples/buggy_repair_app`.

Original fixture defects:

- `src/App.jsx` has a contact form with `name` and `email`, but no `message` field.
- The form has no `onSubmit` handler and no visible confirmation feedback.
- `src/App.css` gives `.wide-banner` `width: 900px`, causing mobile horizontal overflow.
- The CTA button itself does not crash, but the expected behavior mentions click responsiveness and the tester verifies CTA clicks do not create page errors.

Iteration 0 detected:

- `form_has_name_email_message`: failed, missing `message`.
- `submit_shows_feedback`: failed, no visible confirmation.
- `mobile_has_no_horizontal_overflow`: failed, `scrollWidth=956`, `viewportWidth=390`.

Repair applied:

- `src/App.jsx`: added `useState`, `submitted` state, `handleSubmit`, `onSubmit={handleSubmit}`, a `textarea name="message"`, and visible `Message sent` feedback.
- `src/App.css`: added `overflow-x: hidden`, max-width guards, and `.wide-banner` / `.overflow-strip` max-width rules.

Post-repair verification:

- Iteration 1 passed all 8 checks.
- `form_has_name_email_message`: passed.
- `submit_shows_feedback`: passed.
- `mobile_has_no_horizontal_overflow`: passed with `scrollWidth=390`, `viewportWidth=390`.
- `summary.json`: `final_status: passed`, `interaction_correctness_score: 1.0`.

Minor quality note: the deterministic JSX insertion works but indentation is rough around the inserted message field and feedback line. This does not break execution, but it is a patch-quality polish issue.

## 7. Evaluation Audit

The evaluation runner currently measures:

- Executability: npm install, Vite server start, page load, fatal page error status.
- Interaction correctness: fraction of deterministic Playwright checks passed.
- Patch quality: heuristic for repair/editing tasks based on localization, diff size, and targetedness.
- Visual sanity score: non-LLM smoke heuristic for page loaded, nonblank DOM, and mobile overflow.
- Visual quality: placeholder, always `None`.

Latest base evaluation: `runs/evaluation/20260716T075321Z`.

Summary:

- Passing in base mode: dashboard generation, blog generation, three editing tasks.
- Failing in base mode: sample text generation (`submit_shows_feedback`), diagnostic repair, nav repair, tabs repair.
- This is expected for repair tasks in base mode because base mode does not apply browser-feedback repairs.

This evaluation is enough for a basic MVP smoke benchmark. It is not enough for the paper-level evaluation because it lacks WebCompass-style tasks, ablation variants beyond base/browser-feedback, vision-guided tasks, real visual scoring, broader editing/repair coverage, and case-study tables from multiple controlled variants.

## 8. Gap Analysis Against the Paper

Missing or incomplete work:

- More tasks across generation, editing, and repair.
- Broader editing tasks beyond deterministic keyword patterns.
- Vision-guided generation tasks.
- Vision-guided editing tasks.
- Visual reflection using screenshots and a multimodal judge.
- Test synthesis variant that generates task-specific interaction checks.
- Real LLM provider evaluation. An OpenAI provider exists, but it was not used here.
- Stronger OpenAI/local model integration with cost controls and fixtures.
- WebCompass-style benchmark integration or adapter.
- Ablation table for base, browser-feedback, test-synthesis, and visual-reflection variants.
- Case studies with before/after artifacts and failure analysis.
- Final report and presentation materials.
- Cleaner code-patch formatting for deterministic repairs.
- A formal interaction trace input/output format.

## 9. Recommended Next Milestones

### Milestone A: Make current MVP robust

Tasks:

- Fix the base generator's contact form so `sample_text_generation` passes without repair.
- Clean deterministic repair insertion formatting.
- Add regression tests for `submit_shows_feedback` in generated contact forms.
- Add a browser-feedback evaluation run to the documented evaluation snapshot.
- Keep `runs/`, `node_modules/`, `dist/`, and `.venv/` ignored.

Expected outcome:

- Current mock MVP passes all intended sample tasks in browser-feedback mode, and non-repair generation samples do not need avoidable repairs.

### Milestone B: Add OpenAI provider carefully

Tasks:

- Keep mock as default.
- Require explicit `--llm-provider openai`.
- Add a tiny task subset for API smoke testing.
- Add budget controls: max tasks, max iterations, model env var, and dry-run prompt logging.
- Cache or save LLM prompts/responses in run artifacts.

Expected outcome:

- Real LLM use is reproducible and bounded.

Note to avoid wasting API credits:

- First run only one text-generation task, one iteration, with prompt logging enabled and no evaluation batch.

### Milestone C: Expand benchmark tasks

Tasks:

- Add 10-20 local tasks: generation, editing, repair, nav/tabs/forms/layout/runtime failures.
- Add screenshot-backed tasks after schema support exists.
- Add interaction-trace tasks after trace format exists.
- Add WebCompass-style import/adapter if benchmark data is available.

Expected outcome:

- Evaluation can support meaningful aggregate claims instead of only smoke-test claims.

### Milestone D: Prepare paper/report/presentation

Tasks:

- Generate an ablation table for base and browser-feedback now.
- Add placeholder rows for test-synthesis and visual-reflection until implemented.
- Select 3 case studies with run artifacts: generation repair, diagnostic repair, editing.
- Write a concise limitations section that clearly labels deterministic components.
- Build final slides from the verified architecture, metrics, and case studies.

Expected outcome:

- Presentation-ready material that does not overclaim beyond the current MVP.

## 10. Immediate Next Actions

1. Fix generated `ContactForm` to include submit state and visible feedback.
2. Add or update tests so `sample_text_generation` passes in base mode.
3. Run `python3 -m pytest tests/`.
4. Run `python3 -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant base --max-iterations 1`.
5. Run `python3 -m webpilot.evaluation.runner --tasks-dir webpilot/tasks --variant browser-feedback --max-iterations 3`.
6. Document browser-feedback evaluation results in `evaluation/report.md`.
7. Decide whether root `package-lock.json` and `webpilot/examples/buggy_tabs_app/package-lock.json` should be committed or removed; they are currently untracked.
8. Add the next missing variant scaffold only after the current MVP is green.

## Git and Process Hygiene

Process cleanup:

- Initial sandboxed `ps aux | grep vite | grep -v grep` was blocked with `operation not permitted`.
- Elevated process check returned no Vite processes, so no dev server remained running after the audited browser runs.

Git status at audit time:

```text
modified: webpilot/browser/executor.py
untracked: package-lock.json
untracked: webpilot/examples/buggy_tabs_app/package-lock.json
```

Diff stat:

```text
webpilot/browser/executor.py | 3 ++-
```

The existing `executor.py` diff adds `WEBPILOT_HEADED` support for headed Chromium runs. This was present before this audit and was not changed by the audit.

Generated/heavy artifact hygiene:

- `.gitignore` includes `.venv/`, `node_modules/`, `dist/`, `build/`, `runs/*`, and `webpilot/runs/*`.
- `git status --ignored --short runs node_modules dist .venv webpilot/runs` shows `runs/...` and `.venv/` ignored.
- `git ls-files` for `runs`, `node_modules`, `dist`, `.venv`, and `webpilot/runs` reports only `runs/.gitkeep` and `webpilot/runs/.gitkeep`.
- Generated run artifacts are not tracked.
