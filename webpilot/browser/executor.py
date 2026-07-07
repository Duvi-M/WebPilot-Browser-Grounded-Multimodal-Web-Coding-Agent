"""Browser executor built on Playwright and a local Vite dev server."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from webpilot.browser.tester import InteractionTester, TestResult
from webpilot.task_schema import Task


@dataclass(frozen=True)
class ExecutionEvidence:
    workspace_path: Path
    app_url: str
    npm_install_ok: bool
    server_started: bool
    page_loaded: bool
    fatal_page_error: bool
    console_error_count: int
    page_error_count: int
    desktop_screenshot_path: Path
    mobile_screenshot_path: Path
    dom_snapshot_path: Path
    console_logs_path: Path
    page_errors_path: Path
    dev_server_stdout_path: Path
    dev_server_stderr_path: Path
    current_url: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_path": str(self.workspace_path),
            "app_url": self.app_url,
            "npm_install_ok": self.npm_install_ok,
            "server_started": self.server_started,
            "page_loaded": self.page_loaded,
            "fatal_page_error": self.fatal_page_error,
            "console_error_count": self.console_error_count,
            "page_error_count": self.page_error_count,
            "desktop_screenshot_path": str(self.desktop_screenshot_path),
            "mobile_screenshot_path": str(self.mobile_screenshot_path),
            "dom_snapshot_path": str(self.dom_snapshot_path),
            "console_logs_path": str(self.console_logs_path),
            "page_errors_path": str(self.page_errors_path),
            "dev_server_stdout_path": str(self.dev_server_stdout_path),
            "dev_server_stderr_path": str(self.dev_server_stderr_path),
            "current_url": self.current_url,
            "title": self.title,
        }


@dataclass(frozen=True)
class BrowserRunResult:
    evidence: ExecutionEvidence
    test_results: list[TestResult]


class BrowserExecutor:
    """Installs dependencies, starts Vite, opens Chromium, and captures evidence."""

    def __init__(self, timeout_seconds: int = 90) -> None:
        self.timeout_seconds = timeout_seconds

    def execute(self, workspace_path: Path, iteration_dir: Path, task: Task) -> BrowserRunResult:
        iteration_dir.mkdir(parents=True, exist_ok=True)
        paths = _artifact_paths(iteration_dir)
        port = _free_port()
        app_url = f"http://127.0.0.1:{port}"
        console_logs: list[dict[str, str]] = []
        page_errors: list[str] = []
        current_url = ""
        title = ""
        page_loaded = False
        server_started = False
        process: subprocess.Popen[str] | None = None
        install_stdout = ""
        install_stderr = ""

        npm_install_ok = self._npm_install(workspace_path, paths["dev_stdout"], paths["dev_stderr"])
        if npm_install_ok:
            try:
                process = _start_dev_server(workspace_path, port)
                server_started = _wait_until_reachable(app_url, process, timeout_seconds=20)
                if server_started:
                    from playwright.sync_api import sync_playwright

                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch()
                        context = browser.new_context(viewport={"width": 1440, "height": 1000})
                        setattr(context, "_webpilot_page_errors", page_errors)
                        page = context.new_page()
                        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
                        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                        page.goto(app_url, wait_until="networkidle", timeout=30000)
                        page_loaded = True
                        current_url = page.url
                        title = page.title()
                        page.screenshot(path=str(paths["desktop"]), full_page=True)
                        paths["dom"].write_text(page.evaluate("() => document.documentElement.outerHTML"), encoding="utf-8")
                        test_results = InteractionTester().run(page, task)
                        page.set_viewport_size({"width": 390, "height": 844})
                        page.screenshot(path=str(paths["mobile"]), full_page=True)
                        context.close()
                        browser.close()
                else:
                    test_results = []
            except Exception as exc:
                page_errors.append(f"{type(exc).__name__}: {exc}")
                test_results = []
        else:
            test_results = []

        if process is not None:
            install_stdout, install_stderr = _stop_process(process)
        _append_text(paths["dev_stdout"], install_stdout)
        _append_text(paths["dev_stderr"], install_stderr)

        _write_json(paths["console"], console_logs)
        _write_json(paths["errors"], page_errors)
        if not paths["dom"].exists():
            paths["dom"].write_text("", encoding="utf-8")

        evidence = ExecutionEvidence(
            workspace_path=workspace_path,
            app_url=app_url,
            npm_install_ok=npm_install_ok,
            server_started=server_started,
            page_loaded=page_loaded,
            fatal_page_error=bool(page_errors and not page_loaded),
            console_error_count=sum(1 for log in console_logs if log.get("type") == "error"),
            page_error_count=len(page_errors),
            desktop_screenshot_path=paths["desktop"],
            mobile_screenshot_path=paths["mobile"],
            dom_snapshot_path=paths["dom"],
            console_logs_path=paths["console"],
            page_errors_path=paths["errors"],
            dev_server_stdout_path=paths["dev_stdout"],
            dev_server_stderr_path=paths["dev_stderr"],
            current_url=current_url,
            title=title,
        )
        return BrowserRunResult(evidence=evidence, test_results=test_results)

    def _npm_install(self, workspace_path: Path, stdout_path: Path, stderr_path: Path) -> bool:
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except Exception as exc:
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
            return False
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        return result.returncode == 0


def _artifact_paths(iteration_dir: Path) -> dict[str, Path]:
    return {
        "desktop": iteration_dir / "screenshot_desktop.png",
        "mobile": iteration_dir / "screenshot_mobile.png",
        "dom": iteration_dir / "dom_snapshot.html",
        "console": iteration_dir / "console_logs.json",
        "errors": iteration_dir / "page_errors.json",
        "dev_stdout": iteration_dir / "dev_server_stdout.log",
        "dev_stderr": iteration_dir / "dev_server_stderr.log",
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_dev_server(workspace_path: Path, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port)],
        cwd=workspace_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def _wait_until_reachable(url: str, process: subprocess.Popen[str], timeout_seconds: int) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urlopen(url, timeout=1) as response:
                return response.status < 500
        except (URLError, TimeoutError, OSError):
            time.sleep(0.25)
    return False


def _stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            return process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    return process.communicate(timeout=2)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_text(path: Path, text: str) -> None:
    if text:
        with path.open("a", encoding="utf-8") as file:
            file.write(text)

