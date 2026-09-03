"""Bounded Phase 18 usefulness command adapter.

The underlying command owns the evidence semantics and trust gates. This adapter
changes only the final deterministic rendering step: once the base command has
successfully replay-validated the bundle, both renderer byte checks use the
trusted renderer's pure validated-bundle projection rather than triggering two
additional complete immutable replays.
"""

from __future__ import annotations

from typing import Any

from . import phase18_usefulness as _base


class _ValidatedRendererProxy:
    def __init__(self, renderer: Any) -> None:
        pure = getattr(renderer, "_render_validated_multi_asset_temporal_evidence", None)
        if not callable(pure):
            raise RuntimeError("trusted Phase 18 pure renderer is unavailable")
        self._pure = pure

    def render_multi_asset_temporal_evidence(self, _root: Any, bundle: Any) -> str:
        return self._pure(bundle)


def run(runner: Any, github: Any) -> Any:
    """Run the existing proof while avoiding redundant post-validation replays."""
    original_loader = _base._load_contracts

    def bounded_loader(*args: Any, **kwargs: Any) -> dict[str, Any]:
        contracts = original_loader(*args, **kwargs)
        bounded = dict(contracts)
        bounded["renderer"] = _ValidatedRendererProxy(contracts["renderer"])
        return bounded

    _base._load_contracts = bounded_loader
    try:
        return _base.run(runner, github)
    finally:
        _base._load_contracts = original_loader
