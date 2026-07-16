"""Configuration helpers for WebPilot."""

from __future__ import annotations

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs"
DEFAULT_OPENAI_MODEL = os.environ.get("WEBPILOT_OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_OPENAI_MAX_TOKENS = 1200
DEFAULT_OPENAI_TEMPERATURE = 0.2

PLAYWRIGHT_CHROMIUM_SANDBOX_ARGS = ["--no-sandbox", "--disable-setuid-sandbox"]


def chromium_launch_args() -> list[str]:
    """Return Chromium launch args, with sandbox workarounds enabled by default."""

    if os.environ.get("WEBPILOT_DISABLE_CHROMIUM_SANDBOX_ARGS", "").lower() in {"1", "true", "yes"}:
        return []
    return PLAYWRIGHT_CHROMIUM_SANDBOX_ARGS.copy()
