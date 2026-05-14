"""Coherent CryptoPulse static site generator package.

The package exposes one canonical build entry point used by GitHub Actions:

    python -m site_generator

It currently orchestrates the existing generator stages without requiring the
Pages workflow to invoke stacked wrapper scripts directly.
"""

from .pipeline import build

__all__ = ["build"]
