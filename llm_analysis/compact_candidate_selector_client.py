"""Provider-only compact transport wrapper for the Slice 5 selector client."""
from __future__ import annotations

from typing import Any, Mapping

from .candidate_selector import CandidateSelectorClient, SelectorClientResponse
from .candidate_selector_compact_projection import (
    build_compact_candidate_selector_request,
)


class CompactCandidateSelectorClient:
    """Project only the model-visible request; canonical validation stays outside."""

    def __init__(self, inner: CandidateSelectorClient):
        self.inner = inner
        self.compact_requests: list[dict[str, Any]] = []

    @property
    def call_records(self) -> Any:
        return getattr(self.inner, "call_records", ())

    def select(
        self,
        *,
        request: Mapping[str, Any],
        response_schema: Mapping[str, Any],
        repair: Mapping[str, Any] | None,
    ) -> SelectorClientResponse:
        compact = build_compact_candidate_selector_request(request)
        self.compact_requests.append(compact)
        return self.inner.select(
            request=compact,
            response_schema=response_schema,
            repair=repair,
        )
