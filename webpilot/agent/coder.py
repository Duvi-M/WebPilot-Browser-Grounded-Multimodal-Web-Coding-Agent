"""Code generation, workspace preparation, and repair delegation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from webpilot.agent.planner import Plan
from webpilot.agent.repairer import Repairer
from webpilot.llm.base import LLMProvider, LLMProviderError
from webpilot.llm.mock_provider import MockLLMProvider
from webpilot.task_schema import Task


@dataclass(frozen=True)
class CoderResult:
    workspace_path: Path
    generated_files: list[str]
    message: str


class Coder:
    """Creates concrete workspaces from plans."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or MockLLMProvider()

    def code(self, task: Task, plan: Plan, workspace_path: Path) -> CoderResult:
        if task.type == "text_generation":
            if _uses_llm(self.llm_provider):
                return self._generate_react_app_with_llm(task, plan, workspace_path)
            return self._generate_react_app(task, plan, workspace_path)
        if task.type == "editing":
            result = self._copy_existing_workspace(task, workspace_path, "Copied editable repository.")
            edit_result = self.apply_edit(plan, workspace_path)
            generated_files = sorted(set(result.generated_files + edit_result["files_touched"]))
            return CoderResult(
                workspace_path=workspace_path,
                generated_files=generated_files,
                message="Copied repository and applied deterministic edit.",
            )
        return self._copy_repair_workspace(task, workspace_path)

    def apply_repair(self, patch_plan: dict[str, Any], workspace_path: Path | None = None) -> dict[str, Any]:
        if workspace_path is None:
            raise ValueError("workspace_path is required to apply a repair")
        return Repairer().repair(patch_plan, workspace_path)

    def apply_edit(self, plan: Plan, workspace_path: Path | None = None) -> dict[str, Any]:
        if workspace_path is None:
            raise ValueError("workspace_path is required to apply an edit")

        files_touched: list[str] = []
        messages: list[str] = []
        for item in plan.items:
            if item.name == "TestimonialsSection":
                files_touched.extend(_apply_testimonials_edit(workspace_path))
                messages.append("Added testimonials section after pricing.")
            elif item.name == "FAQSection":
                files_touched.extend(_apply_faq_edit(workspace_path))
                messages.append("Added FAQ section before contact.")
            elif item.name == "CTAButton":
                files_touched.extend(_apply_cta_button_edit(workspace_path, item.details.get("label", "Get started")))
                messages.append("Added CTA button to the hero section.")
            else:
                messages.append(f"No deterministic edit implemented for {item.name}.")

        return {
            "edits_applied": bool(files_touched),
            "files_touched": sorted(set(files_touched)),
            "messages": messages,
        }

    def _generate_react_app(self, task: Task, plan: Plan, workspace_path: Path) -> CoderResult:
        workspace_path.mkdir(parents=True, exist_ok=True)
        (workspace_path / "src" / "components").mkdir(parents=True, exist_ok=True)

        components = {item.name for item in plan.items}
        if "HeroSection" not in components:
            components.add("HeroSection")

        files: dict[str, str] = {
            "package.json": _package_json(),
            "vite.config.js": _vite_config(),
            "index.html": _index_html(),
            "src/main.jsx": _main_jsx(),
            "src/App.jsx": _app_jsx(components),
            "src/App.css": _app_css(),
        }

        if "HeroSection" in components:
            files["src/components/HeroSection.jsx"] = _hero_section(task)
        if "PricingSection" in components:
            files["src/components/PricingSection.jsx"] = _pricing_section()
        if "ContactForm" in components:
            files["src/components/ContactForm.jsx"] = _contact_form()
        if "AppShell" in components:
            files["src/components/AppShell.jsx"] = _app_shell(task)

        generated: list[str] = []
        for relative_path, content in files.items():
            file_path = workspace_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            generated.append(relative_path)

        return CoderResult(
            workspace_path=workspace_path,
            generated_files=sorted(generated),
            message="Generated a Vite + React workspace.",
        )

    def _generate_react_app_with_llm(self, task: Task, plan: Plan, workspace_path: Path) -> CoderResult:
        workspace_path.mkdir(parents=True, exist_ok=True)
        prompt = _code_prompt(task, plan)
        try:
            files = _parse_file_map(self.llm_provider.complete(prompt))
        except (json.JSONDecodeError, ValueError, LLMProviderError) as exc:
            raise LLMProviderError(f"LLM coder returned invalid file JSON: {exc}") from exc

        generated: list[str] = []
        for relative_path, content in files.items():
            file_path = _safe_workspace_path(workspace_path, relative_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            generated.append(relative_path)

        return CoderResult(
            workspace_path=workspace_path,
            generated_files=sorted(generated),
            message="Generated a Vite + React workspace with LLM provider.",
        )

    def _copy_repair_workspace(self, task: Task, workspace_path: Path) -> CoderResult:
        return self._copy_existing_workspace(task, workspace_path, "Copied diagnostic repair repository.")

    def _copy_existing_workspace(self, task: Task, workspace_path: Path, message: str) -> CoderResult:
        if task.repo_path is None:
            raise ValueError(f"{task.type} tasks require repo_path")

        source = Path(task.repo_path).expanduser().resolve()
        if not source.exists() or not source.is_dir():
            raise ValueError(f"repo_path does not exist or is not a directory: {source}")

        if workspace_path.exists():
            shutil.rmtree(workspace_path)
        shutil.copytree(source, workspace_path, ignore=shutil.ignore_patterns(".git", "node_modules", "dist", "build"))

        copied_files = [
            str(path.relative_to(workspace_path))
            for path in workspace_path.rglob("*")
            if path.is_file()
        ]
        return CoderResult(
            workspace_path=workspace_path,
            generated_files=sorted(copied_files),
            message=message,
        )


def _apply_testimonials_edit(workspace_path: Path) -> list[str]:
    app_path = workspace_path / "src" / "App.jsx"
    css_path = workspace_path / "src" / "App.css"
    component_path = workspace_path / "src" / "components" / "TestimonialsSection.jsx"

    component_path.parent.mkdir(parents=True, exist_ok=True)
    component_path.write_text(_testimonials_section(), encoding="utf-8")
    _ensure_import(app_path, "TestimonialsSection")
    _insert_component_after_section(app_path, "pricing-section", "TestimonialsSection")
    _append_css_once(css_path, "testimonials-section", _testimonials_css())
    return [
        "src/App.jsx",
        "src/App.css",
        "src/components/TestimonialsSection.jsx",
    ]


def _apply_faq_edit(workspace_path: Path) -> list[str]:
    app_path = workspace_path / "src" / "App.jsx"
    css_path = workspace_path / "src" / "App.css"
    component_path = workspace_path / "src" / "components" / "FAQSection.jsx"

    component_path.parent.mkdir(parents=True, exist_ok=True)
    component_path.write_text(_faq_section(), encoding="utf-8")
    _ensure_import(app_path, "FAQSection")
    _insert_component_before_section(app_path, "contact-section", "FAQSection")
    _append_css_once(css_path, "faq-section", _faq_css())
    return ["src/App.jsx", "src/App.css", "src/components/FAQSection.jsx"]


def _apply_cta_button_edit(workspace_path: Path, label: Any) -> list[str]:
    app_path = workspace_path / "src" / "App.jsx"
    source = app_path.read_text(encoding="utf-8")
    if "data-webpilot-added-cta" in source:
        return ["src/App.jsx"]
    safe_label = str(label) if isinstance(label, str) and label.strip() else "Get started"
    button = f'\n        <button type="button" data-webpilot-added-cta>{safe_label}</button>'
    marker = "</h1>"
    if marker not in source:
        raise ValueError("Could not find a hero heading to place the CTA button after.")
    app_path.write_text(source.replace(marker, marker + button, 1), encoding="utf-8")
    return ["src/App.jsx"]


def _ensure_import(app_path: Path, component_name: str) -> None:
    source = app_path.read_text(encoding="utf-8")
    import_line = f"import {{ {component_name} }} from './components/{component_name}.jsx';"
    if import_line in source:
        return
    if source.startswith("import "):
        lines = source.splitlines()
        insert_at = 0
        for index, line in enumerate(lines):
            if line.startswith("import "):
                insert_at = index + 1
        lines.insert(insert_at, import_line)
        app_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    app_path.write_text(import_line + "\n\n" + source, encoding="utf-8")


def _insert_component_after_section(app_path: Path, section_class: str, component_name: str) -> None:
    source = app_path.read_text(encoding="utf-8")
    component_tag = f"<{component_name} />"
    if component_tag in source:
        return
    marker_index = source.find(section_class)
    if marker_index == -1:
        raise ValueError(f"Could not find section marker {section_class!r} in src/App.jsx")
    closing_index = source.find("</section>", marker_index)
    if closing_index == -1:
        raise ValueError(f"Could not find closing section after {section_class!r}")
    insert_at = closing_index + len("</section>")
    source = source[:insert_at] + f"\n\n      {component_tag}" + source[insert_at:]
    app_path.write_text(source, encoding="utf-8")


def _insert_component_before_section(app_path: Path, section_class: str, component_name: str) -> None:
    source = app_path.read_text(encoding="utf-8")
    component_tag = f"<{component_name} />"
    if component_tag in source:
        return
    marker_index = source.find(section_class)
    if marker_index == -1:
        raise ValueError(f"Could not find section marker {section_class!r} in src/App.jsx")
    section_start = source.rfind("<section", 0, marker_index)
    if section_start == -1:
        raise ValueError(f"Could not find section start before {section_class!r}")
    source = source[:section_start] + f"{component_tag}\n\n      " + source[section_start:]
    app_path.write_text(source, encoding="utf-8")


def _append_css_once(css_path: Path, marker: str, css: str) -> None:
    source = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    if marker in source:
        return
    css_path.write_text(source.rstrip() + "\n\n" + css.lstrip(), encoding="utf-8")


def _testimonials_section() -> str:
    return """const testimonials = [
  {
    name: 'Maya Chen',
    quote: 'The new planning flow helped our team ship with far fewer status meetings.',
  },
  {
    name: 'Jordan Lee',
    quote: 'We finally have one calm place to see priorities, pricing, and next steps.',
  },
];

export function TestimonialsSection() {
  return (
    <section className="testimonials-section" aria-labelledby="testimonials-title">
      <div className="section-heading">
        <p className="eyebrow">Testimonials</p>
        <h2 id="testimonials-title">Teams trust WebPilot-ready workflows</h2>
      </div>
      <div className="testimonial-grid">
        {testimonials.map((testimonial) => (
          <article className="testimonial-card" key={testimonial.name}>
            <p>{testimonial.quote}</p>
            <h3>{testimonial.name}</h3>
          </article>
        ))}
      </div>
    </section>
  );
}
"""


def _testimonials_css() -> str:
    return """.testimonials-section {
  background: #f8fafc;
  padding: 48px 24px;
}

.testimonial-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.testimonial-card {
  background: #ffffff;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  padding: 20px;
}

.testimonial-card p {
  color: #334155;
  line-height: 1.7;
}

@media (max-width: 760px) {
  .testimonial-grid {
    grid-template-columns: 1fr;
  }
}
"""


def _faq_section() -> str:
    return """const faqs = [
  { question: 'Can we start small?', answer: 'Yes, the app supports lightweight landing-page edits first.' },
  { question: 'Does this require an API key?', answer: 'No, deterministic editing works in mock mode.' },
  { question: 'Can browser feedback still run?', answer: 'Yes, the normal browser checks still execute afterward.' },
];

export function FAQSection() {
  return (
    <section className="faq-section" aria-labelledby="faq-title">
      <div className="section-heading">
        <p className="eyebrow">FAQ</p>
        <h2 id="faq-title">Common questions</h2>
      </div>
      {faqs.map((faq) => (
        <article className="faq-item" key={faq.question}>
          <h3>{faq.question}</h3>
          <p>{faq.answer}</p>
        </article>
      ))}
    </section>
  );
}
"""


def _faq_css() -> str:
    return """.faq-section {
  background: #ffffff;
  padding: 48px 24px;
}

.faq-item {
  border-top: 1px solid #dbe3ee;
  max-width: 760px;
  padding: 18px 0;
}
"""


def _package_json() -> str:
    return """{
  "engines": {
    "node": ">=18"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.7",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {}
}
"""


def _vite_config() -> str:
    return """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
});
"""


def _index_html() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>WebPilot Generated App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""


def _main_jsx() -> str:
    return """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './App.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
"""


def _app_jsx(components: set[str]) -> str:
    ordered = [name for name in ["HeroSection", "PricingSection", "ContactForm", "AppShell"] if name in components]
    imports = "\n".join(f"import {{ {name} }} from './components/{name}.jsx';" for name in ordered)
    renders = "\n        ".join(f"<{name} />" for name in ordered)
    return f"""{imports}

export default function App() {{
  return (
    <main className="app">
      {renders}
    </main>
  );
}}
"""


def _hero_section(task: Task) -> str:
    title = _infer_title(task.instruction)
    return f"""export function HeroSection() {{
  return (
    <section className="hero-section">
      <p className="eyebrow">Task management for focused teams</p>
      <h1>{title}</h1>
      <p className="hero-copy">
        Plan work, align priorities, and keep projects moving with a responsive workspace
        designed for everyday execution.
      </p>
      <a className="cta-button" href="#contact">Start planning today</a>
    </section>
  );
}}
"""


def _pricing_section() -> str:
    return """const tiers = [
  { name: 'Starter', price: '$12', features: ['Shared task boards', 'Weekly planning', 'Basic reporting'] },
  { name: 'Pro', price: '$29', features: ['Automation rules', 'Timeline views', 'Priority support'] },
  { name: 'Team', price: '$59', features: ['Advanced permissions', 'Portfolio tracking', 'SAML-ready access'] },
];

export function PricingSection() {
  return (
    <section className="pricing-section" aria-labelledby="pricing-title">
      <div className="section-heading">
        <p className="eyebrow">Pricing</p>
        <h2 id="pricing-title">Plans that scale with your workload</h2>
      </div>
      <div className="pricing-grid">
        {tiers.map((tier) => (
          <article className="pricing-card" key={tier.name}>
            <h3>{tier.name}</h3>
            <p className="price"><span>{tier.price}</span> / user</p>
            <ul>
              {tier.features.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
            <button type="button">Choose {tier.name}</button>
          </article>
        ))}
      </div>
    </section>
  );
}
"""


def _contact_form() -> str:
    return """export function ContactForm() {
  return (
    <section className="contact-section" id="contact" aria-labelledby="contact-title">
      <div className="section-heading">
        <p className="eyebrow">Contact</p>
        <h2 id="contact-title">Tell us what your team needs</h2>
      </div>
      <form className="contact-form">
        <label>
          Name
          <input name="name" type="text" placeholder="Alex Morgan" autoComplete="name" />
        </label>
        <label>
          Email
          <input name="email" type="email" placeholder="alex@example.com" autoComplete="email" />
        </label>
        <label>
          Message
          <textarea name="message" placeholder="What workflow should we help you improve?" rows="5" />
        </label>
        <button type="submit">Send message</button>
      </form>
    </section>
  );
}
"""


def _app_shell(task: Task) -> str:
    return f"""export function AppShell() {{
  return (
    <section className="hero-section">
      <p className="eyebrow">Generated from task</p>
      <h1>{_infer_title(task.instruction)}</h1>
      <p className="hero-copy">{task.instruction}</p>
    </section>
  );
}}
"""


def _app_css() -> str:
    return """:root {
  color: #172033;
  background: #f6f8fb;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
input,
textarea {
  font: inherit;
}

.app {
  min-height: 100vh;
}

.hero-section,
.pricing-section,
.contact-section {
  padding: 64px max(24px, calc((100vw - 1120px) / 2));
}

.hero-section {
  background: linear-gradient(135deg, #ffffff 0%, #eaf2ff 52%, #e6f7ef 100%);
}

.eyebrow {
  color: #246b55;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0;
  margin: 0 0 12px;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  font-size: clamp(2.4rem, 5vw, 4.5rem);
  line-height: 1;
  margin-bottom: 20px;
  max-width: 820px;
}

h2 {
  font-size: 2rem;
  line-height: 1.15;
}

.hero-copy {
  color: #526072;
  font-size: 1.15rem;
  line-height: 1.7;
  max-width: 680px;
}

.cta-button,
button {
  align-items: center;
  background: #246b55;
  border: 0;
  border-radius: 8px;
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  font-weight: 700;
  justify-content: center;
  min-height: 44px;
  padding: 0 18px;
  text-decoration: none;
}

.section-heading {
  margin-bottom: 28px;
  max-width: 680px;
}

.pricing-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.pricing-card {
  background: #ffffff;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  padding: 24px;
}

.price {
  color: #526072;
}

.price span {
  color: #172033;
  font-size: 2.4rem;
  font-weight: 800;
}

.pricing-card ul {
  color: #526072;
  line-height: 1.8;
  padding-left: 20px;
}

.contact-section {
  background: #ffffff;
}

.contact-form {
  display: grid;
  gap: 16px;
  max-width: 640px;
}

.contact-form label {
  color: #334155;
  display: grid;
  font-weight: 700;
  gap: 8px;
}

.contact-form input,
.contact-form textarea {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 12px 14px;
  width: 100%;
}

@media (max-width: 760px) {
  .hero-section,
  .pricing-section,
  .contact-section {
    padding: 44px 20px;
  }

  .pricing-grid {
    grid-template-columns: 1fr;
  }
}
"""


def _infer_title(instruction: str) -> str:
    if "task management" in instruction.lower():
        return "Manage every task without losing momentum"
    return "A focused web experience generated by WebPilot"


def _uses_llm(provider: LLMProvider) -> bool:
    return getattr(provider, "provider_name", "mock") != "mock"


def _code_prompt(task: Task, plan: Plan) -> str:
    return f"""Generate a minimal runnable Vite + React app for this WebPilot task.

Return JSON only: an object mapping relative file paths to full file contents.
Required paths:
- package.json
- vite.config.js
- index.html
- src/main.jsx
- src/App.jsx
- src/App.css

You may add component files under src/components/.
Do not include markdown fences or explanations.
Use React 18, Vite, and JavaScript JSX.
The app must satisfy the task and plan.

Task:
{json.dumps(task.to_dict(), indent=2)}

Plan:
{json.dumps(plan.to_dict(), indent=2)}
"""


def _parse_file_map(raw: str) -> dict[str, str]:
    data = json.loads(_strip_json_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("file output must be a JSON object")
    if len(data) > 32:
        raise ValueError("LLM output contains too many files")

    required = {"package.json", "vite.config.js", "index.html", "src/main.jsx", "src/App.jsx", "src/App.css"}
    missing = required.difference(data)
    if missing:
        raise ValueError(f"LLM output missing required files: {sorted(missing)}")

    files: dict[str, str] = {}
    for relative_path, content in data.items():
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("file paths must be non-empty strings")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"file content for {relative_path} must be non-empty")
        if len(content) > 100_000:
            raise ValueError(f"file content for {relative_path} is too large")
        files[relative_path] = content
    return files


def _safe_workspace_path(workspace_path: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe LLM file path: {relative_path}")
    target = (workspace_path / path).resolve()
    workspace = workspace_path.resolve()
    if workspace not in target.parents and target != workspace:
        raise ValueError(f"Unsafe LLM file path outside workspace: {relative_path}")
    return target


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text
