# WebPilot: Browser-Grounded Multimodal Web Coding Agent

[Прогресс по требованиям проекта](PROJECT_PROGRESS_RU.md)

WebPilot is a research/prototype project for a web coding agent that closes the loop between code generation and real browser evidence.

The MVP loop is:

```text
implement -> execute -> inspect -> repair
```

## Project Flow

```mermaid
flowchart LR
    task["Task input<br/>generation, editing,<br/>or diagnostic repair"] --> planner["Planner<br/>structured implementation plan"]
    planner --> coder["Coder<br/>generate app, copy/edit repo,<br/>or copy repair workspace"]
    coder --> workspace["Generated workspace<br/>package.json, React source, CSS"]

    workspace --> executor["Browser Executor<br/>npm install + Vite dev server<br/>Playwright Chromium"]
    executor --> evidence["Browser evidence<br/>screenshots, DOM snapshot,<br/>console logs, page errors"]
    executor --> tester["Interaction Tester<br/>load, buttons, forms,<br/>submit feedback, mobile overflow"]

    evidence --> reflector["Reflector<br/>classify failures"]
    tester --> reflector

    reflector --> decision{"All checks pass?"}
    decision -- "yes" --> summary["summary.json<br/>executability + interaction score"]
    decision -- "no, base variant" --> summary
    decision -- "no, browser-feedback<br/>and iterations remain" --> repairer["Repairer<br/>deterministic localized patch"]
    repairer --> workspace

    summary --> evaluation["Evaluation runner<br/>JSON + Markdown tables"]
```

Expected outcome: a local research prototype that can create or copy a front-end app, run it in a real browser, collect evidence, test basic interactions, repair known failures, and save auditable run artifacts.

## What Step 2 Supports

- Text-guided generation of a minimal Vite + React app.
- Instruction-guided editing of an existing Vite + React app for a small deterministic pattern set.
- Diagnostic repair using a local broken fixture.
- Browser execution with Playwright and Chromium.
- Dynamic Vite dev-server ports.
- Screenshot capture for desktop and mobile viewports.
- DOM snapshot capture.
- Console log and page error capture.
- Basic Playwright interaction checks.
- Deterministic browser-feedback repairs for known failure types.
- Optional OpenAI-backed planning and code generation for `text_generation` tasks.
- `base` and `browser-feedback` variants.
- A small evaluation runner over JSON tasks.

Out of scope for this MVP: general-purpose editing, vision-guided generation, vision-guided editing, local model providers, WebCompass integration, visual-reflection/test-synthesis variants, backend, database, authentication, deployment.

## Known Limitations

- The repairer handles only a fixed set of hardcoded failure patterns: missing form fields, missing submit feedback, missing submit handler, and mobile horizontal overflow. Other failures are reported as `no_automated_repair_available`.
- Editing currently handles only a fixed set of deterministic requested-change patterns: add testimonials, add FAQ, and add a simple CTA button. It is not a general code editing engine yet.
- With `--llm-provider openai`, Planner and Coder become LLM-driven for generation tasks, but the Repairer remains deterministic for now.
- Chromium is launched with sandbox workaround args by default: `--no-sandbox` and `--disable-setuid-sandbox`. Set `WEBPILOT_DISABLE_CHROMIUM_SANDBOX_ARGS=1` to disable those args on systems where the browser sandbox works normally.
- `patch_quality` and `visual_quality` are placeholder metrics and currently return `None`.
- Generated repairs are deterministic string edits, not robust AST-aware code transformations.

## Requirements

- Python `>=3.10`
- Node.js `>=18`
- Playwright Python package `1.56.0`
- Generated apps use Vite `^6.0.7`, React `^18.3.1`, React DOM `^18.3.1`, and `@vitejs/plugin-react` `^4.3.4`

## Installation

```bash
pip install -e ".[dev]"
python -m playwright install chromium
```

## Run Sample Text Generation

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant base --max-iterations 1
```

Mock mode is the default and does not call any external API:

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant base --max-iterations 1 --llm-provider mock
```

To use OpenAI for planning and generation, set an API key and opt in explicitly. Real API calls cost money.

```bash
export OPENAI_API_KEY="..."
python -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant browser-feedback --max-iterations 3 --llm-provider openai
```

## Run Browser Feedback

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant browser-feedback --max-iterations 3
```

## Run Diagnostic Repair

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_diagnostic_repair.json --variant browser-feedback --max-iterations 3
```

The diagnostic task copies `webpilot/examples/buggy_repair_app` into the run workspace, executes it, detects missing form/feedback/overflow issues, and applies deterministic repairs when possible.

## Run Editing

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_editing_task.json --variant base --max-iterations 1
```

The editing task copies `webpilot/examples/editable_landing_app` into the run workspace and applies a deterministic localized edit. The sample adds `TestimonialsSection.jsx`, imports it into `src/App.jsx`, renders it below pricing, and appends matching CSS.

## Run Evaluation

```bash
python -m webpilot.evaluation.runner --tasks-dir webpilot/tasks --variant base --max-iterations 1
```

Evaluation output is written under:

```text
runs/evaluation/<timestamp>/
```

## Inspect Artifacts

Each CLI run writes artifacts under:

```text
runs/<task_id>/<timestamp>/
```

Each iteration writes:

```text
iteration_<n>/
  screenshot_desktop.png
  screenshot_mobile.png
  dom_snapshot.html
  console_logs.json
  page_errors.json
  dev_server_stdout.log
  dev_server_stderr.log
  test_results.json
  reflection.json
  repair_plan.json
```

`repair_plan.json` is present only when a repair is attempted. The final `summary.json` includes executability, interaction correctness, failures found, repair attempts, and the final workspace path.

## Tests

```bash
python -m pytest tests/
```

The CLI smoke test skips explicitly if `npm`, the Playwright Python package, or the Chromium browser binary is missing.
