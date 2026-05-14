"""Canonical CryptoPulse site build pipeline.

This module gives the project one coherent build entry point while preserving
existing generated output behaviour. The older scripts remain available as
compatibility shims, but GitHub Actions and documentation should invoke this
package instead of chaining wrapper scripts directly.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"


def ensure_script_import_path() -> None:
    """Allow the legacy script modules to be imported as implementation stages."""
    scripts_path = str(SCRIPTS_DIR)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)


def implementation_stage() -> ModuleType:
    """Return the current full-feature implementation stage.

    The search-filter wrapper is the latest stage in the historical chain and
    preserves all currently shipped output: base pages, search, data-quality
    panels, mobile UX, brief-at-a-glance panels, structured sources, and archive
    filters. This package centralises orchestration so workflows no longer need
    to know about that internal layering.
    """
    ensure_script_import_path()
    return importlib.import_module("build_pages_site_search_filters")


def build() -> None:
    """Build the complete CryptoPulse static site."""
    stage = implementation_stage()
    stage_build: Callable[[], None] = getattr(stage, "build")
    stage_build()


if __name__ == "__main__":
    build()
