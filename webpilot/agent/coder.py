"""Code generation, workspace preparation, and repair delegation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any

from webpilot.agent.planner import Plan
from webpilot.agent.repairer import Repairer
from webpilot.task_schema import Task


@dataclass(frozen=True)
class CoderResult:
    workspace_path: Path
    generated_files: list[str]
    message: str


class Coder:
    """Creates concrete workspaces from plans."""

    def code(self, task: Task, plan: Plan, workspace_path: Path) -> CoderResult:
        if task.type == "text_generation":
            return self._generate_react_app(task, plan, workspace_path)
        return self._copy_repair_workspace(task, workspace_path)

    def apply_repair(self, patch_plan: dict[str, Any], workspace_path: Path | None = None) -> dict[str, Any] | str:
        if workspace_path is None:
            return "not implemented in step 1"
        return Repairer().repair(patch_plan, workspace_path)

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

    def _copy_repair_workspace(self, task: Task, workspace_path: Path) -> CoderResult:
        if task.repo_path is None:
            raise ValueError("diagnostic_repair tasks require repo_path")

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
            message="Copied diagnostic repair repository; repair patching is deferred to step 2.",
        )


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
