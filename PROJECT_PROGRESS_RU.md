# Прогресс по требованиям проекта

Этот документ кратко показывает, что уже реализовано в WebPilot, что покрывает требования из проектного paper, и что еще нужно сделать команде.

## Общий статус

- [x] Создан рабочий GitHub/project skeleton для WebPilot.
- [x] Реализован runnable MVP без API-ключей.
- [x] Реализован browser-grounded цикл для локальных front-end задач.
- [x] Добавлены артефакты запусков: планы, screenshots, DOM, console logs, page errors, test results, reflections, repair plans, summaries.
- [x] Добавлены тесты и smoke test для CLI.
- [ ] Проект пока не является полной WebCompass-style benchmark системой.
- [ ] Vision-guided задачи, видео/trace input и multimodal judge пока не реализованы.

## Требования paper и текущий прогресс

### Agent loop: implement -> execute -> inspect -> repair

- [x] Planner читает задачу и строит структурированный план.
- [x] Coder генерирует Vite + React приложение для `text_generation`.
- [x] Coder копирует существующий repo для `diagnostic_repair`.
- [x] Browser Executor запускает локальный проект в реальном Chromium через Playwright.
- [x] Interaction Tester выполняет базовые browser checks.
- [x] Reflector классифицирует ошибки по evidence и test results.
- [x] Repairer применяет deterministic template-based repairs.
- [x] Loop повторяется до успеха или до `--max-iterations`.
- [ ] Нет полноценного LLM-based repair reasoning.
- [ ] Нет поддержки сложных multi-step workflows вроде shopping cart, auth flow, drag-and-drop.

### Поддерживаемые task types

- [x] `text_generation`: генерация минимального runnable Vite + React приложения.
- [x] `diagnostic_repair`: копирование сломанного repo и deterministic repair.
- [ ] `text_guided_editing`: полноценное редактирование существующего repo еще не реализовано.
- [ ] `vision_guided_generation`: генерация по screenshot еще не реализована.
- [ ] `vision_guided_editing`: редактирование по screenshot еще не реализовано.
- [ ] `visual_diagnostic_repair`: multimodal visual repair еще не реализован.
- [ ] Interaction trace input еще не реализован.

### Архитектура из paper

- [x] Planner: `webpilot/agent/planner.py`
- [x] Coder: `webpilot/agent/coder.py`
- [x] Browser Executor: `webpilot/browser/executor.py`
- [x] Interaction Tester: `webpilot/browser/tester.py`
- [x] Reflector: `webpilot/agent/reflector.py`
- [x] Repairer: `webpilot/agent/repairer.py`
- [x] Agent Loop: `webpilot/agent/loop.py`
- [x] Run Logger: `webpilot/logging_utils/run_logger.py`
- [x] Evaluation metrics: `webpilot/evaluation/metrics.py`
- [x] Evaluation runner: `webpilot/evaluation/runner.py`

### Browser-grounded feedback signals

- [x] Build/install signal: `npm install` result is recorded.
- [x] Runtime/server signal: Vite dev server startup is recorded.
- [x] Browser load signal: page loaded status is recorded.
- [x] Screenshots: desktop and mobile screenshots are saved.
- [x] DOM snapshot: `document.documentElement.outerHTML` is saved.
- [x] Console logs: browser console messages are saved.
- [x] Page errors: Playwright page errors are saved.
- [x] Interaction test results are saved.
- [x] Dynamic port selection is implemented.
- [x] Dev-server cleanup is implemented after each iteration.
- [ ] Visual quality is not yet judged by a multimodal model.
- [ ] Screenshot comparison against reference images is not implemented.

### Interaction testing

- [x] Check that the page loads.
- [x] Check expected visible sections/text.
- [x] Check buttons exist.
- [x] Check buttons are clickable without page errors.
- [x] Check contact form fields: name, email, message.
- [x] Check CTA click does not crash.
- [x] Check submit feedback appears.
- [x] Check mobile horizontal overflow.
- [ ] Complex navigation, filters, sorting, modals and drag-and-drop are not implemented yet.
- [ ] LLM-synthesized Playwright tests are not implemented yet.

### Deterministic repair

- [x] Repair missing form fields.
- [x] Repair missing submit handler.
- [x] Repair missing visible submit feedback.
- [x] Repair mobile horizontal overflow via CSS guards.
- [x] Save `repair_plan.json` with attempted repairs, applied repairs, modified files and diffs.
- [x] Unknown failures are recorded without crashing.
- [ ] Unified-diff patch application for arbitrary code edits is not implemented yet.
- [ ] Root-cause repair for general JavaScript/runtime errors is not implemented yet.

### Variants / ablation study

- [x] `base`: one execution attempt, collects browser evidence, does not repair.
- [x] `browser-feedback`: collects evidence, reflects, repairs and repeats.
- [ ] `test-synthesis`: not implemented.
- [ ] `visual-reflection`: not implemented.
- [ ] Full ablation table over a large benchmark is not implemented yet.

### Evaluation metrics from paper

- [x] Executability: npm install, server started, page loaded, no fatal page error.
- [x] Interaction correctness: fraction of interaction checks passed.
- [x] Evaluation runner writes JSON and Markdown summary tables.
- [ ] Visual quality metric is a placeholder.
- [ ] Patch quality metric is a placeholder.
- [ ] Qualitative case-study report is not written yet.

### Deliverables

- [x] GitHub repository with WebPilot implementation.
- [x] Task runner via CLI:
  `python -m webpilot.cli run --task ...`
- [x] Browser automation based on Playwright.
- [x] Logging system for code, plans, screenshots, DOM snapshots, console logs, page errors, test results and repair plans.
- [x] Evaluation runner:
  `python -m webpilot.evaluation.runner --tasks-dir webpilot/tasks ...`
- [ ] Final research report with quantitative ablations is not done yet.
- [ ] Final presentation is not done yet.

## Что сейчас можно запустить

### Text generation, base variant

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant base --max-iterations 1
```

### Text generation, browser-feedback variant

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_text_generation.json --variant browser-feedback --max-iterations 3
```

### Diagnostic repair

```bash
python -m webpilot.cli run --task webpilot/tasks/sample_diagnostic_repair.json --variant browser-feedback --max-iterations 3
```

### Evaluation runner

```bash
python -m webpilot.evaluation.runner --tasks-dir webpilot/tasks --variant base --max-iterations 1
```

### Tests

```bash
python -m pytest tests/
```

## Текущее содержимое проекта

- [x] `webpilot/tasks/sample_text_generation.json`
- [x] `webpilot/tasks/sample_diagnostic_repair.json`
- [x] `webpilot/examples/buggy_repair_app/`
- [x] `webpilot/browser/`
- [x] `webpilot/agent/`
- [x] `webpilot/evaluation/`
- [x] `tests/`
- [x] `README.md`

## Что важно сделать дальше

- [ ] Добавить больше task fixtures: generation, editing, repair.
- [ ] Реализовать `text_guided_editing` для существующих repositories.
- [ ] Добавить поддержку reference screenshot input.
- [ ] Добавить multimodal visual reflection для оценки layout/design качества.
- [ ] Добавить test-synthesis variant для генерации Playwright checks.
- [ ] Улучшить repairer: более аккуратные JSX edits, форматирование, более широкий набор failure types.
- [ ] Добавить patch quality scoring.
- [ ] Подготовить ablation report: `base` vs `browser-feedback` vs future variants.
- [ ] Подготовить case studies: build error fix, interaction bug fix, visual/layout fix, failure case.
- [ ] Подготовить final presentation.

## Ограничения текущего MVP

- [x] Проект сфокусирован на front-end, как указано в paper.
- [x] Backend, database, authentication и deployment не реализуются в этом MVP.
- [x] Browser interactions выполняются на локальных generated apps или local fixtures.
- [ ] Нет защиты/анализа лицензий для внешних screenshots или web prototypes.
- [ ] Нет интеграции с полноценным WebCompass dataset.

