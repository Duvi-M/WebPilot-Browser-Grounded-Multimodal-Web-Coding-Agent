# WebPilot: Browser-Grounded Multimodal Web Coding Agent

WebPilot is a research/prototype project for a web coding agent that closes the loop between code generation and real browser evidence.

The MVP loop is:

```text
implement -> execute -> inspect -> repair
```

## What Step 2 Supports

- Text-guided generation of a minimal Vite + React app.
- Diagnostic repair using a local broken fixture.
- Browser execution with Playwright and Chromium.
- Dynamic Vite dev-server ports.
- Screenshot capture for desktop and mobile viewports.
- DOM snapshot capture.
- Console log and page error capture.
- Basic Playwright interaction checks.
- Deterministic browser-feedback repairs for known failure types.
- `base` and `browser-feedback` variants.
- A small evaluation runner over JSON tasks.

Out of scope for this MVP: full editing tasks, vision-guided generation, vision-guided editing, OpenAI/local model providers, WebCompass integration, visual-reflection/test-synthesis variants, backend, database, authentication, deployment.

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

## Run Browser Feedback

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant browser-feedback --max-iterations 3
```

## Run Diagnostic Repair

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_diagnostic_repair.json --variant browser-feedback --max-iterations 3
```

The diagnostic task copies `webpilot/examples/buggy_repair_app` into the run workspace, executes it, detects missing form/feedback/overflow issues, and applies deterministic repairs when possible.

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
