#!/usr/bin/env python3
"""Render validated Phase 13 observation-hour evidence for Phase 15 public use."""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from crypto_observation_hour_series import (
    ObservationHourSeriesError,
    validate_observation_hour_series,
)
from phase15_public_temporal_evidence import (
    PUBLIC_SERIES_KEY,
    PUBLIC_SERIES_KIND,
    PUBLIC_SLOT_COUNT,
    Phase15PublicTemporalEvidenceError,
    _enforce_public_series_shape,
)

WIDTH = 960
HEIGHT = 420
LEFT = Decimal("80")
RIGHT = Decimal("930")
TOP = Decimal("70")
BOTTOM = Decimal("330")
Q = Decimal("0.01")


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _coord(value: Decimal) -> str:
    text = format(value.quantize(Q, rounding=ROUND_HALF_UP), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _x(index: int, count: int) -> Decimal:
    if count <= 1:
        return (LEFT + RIGHT) / 2
    return LEFT + (RIGHT - LEFT) * Decimal(index) / Decimal(count - 1)


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None or not isinstance(value, (int, float, str)):
        raise Phase15PublicTemporalEvidenceError("validated metric datum must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise Phase15PublicTemporalEvidenceError("validated metric datum must be finite")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise Phase15PublicTemporalEvidenceError("validated metric datum must be numeric") from exc
    if not result.is_finite():
        raise Phase15PublicTemporalEvidenceError("validated metric datum must be finite")
    return result


def _display(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _json(value: Any) -> str:
    if value is None:
        return "—"
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _comparison(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry["value"] if entry.get("value") is not None else entry["gap"]
    comparison = payload.get("comparison") if isinstance(payload, dict) else None
    return comparison if isinstance(comparison, dict) else {}


def _is_degraded(entry: dict[str, Any]) -> bool:
    comparison = _comparison(entry)
    return any(
        isinstance(comparison.get(side), dict)
        and comparison[side].get("quality_status") == "valid-degraded"
        for side in ("current", "predecessor")
    )


def _segments(entries: list[dict[str, Any]]) -> list[list[int]]:
    """Connect numeric points only where Phase 13 records exact continuity."""
    output: list[list[int]] = []
    current: list[int] = []
    for index, entry in enumerate(entries):
        if entry.get("value") is None:
            if current:
                output.append(current)
                current = []
            continue
        _number(entry["value"].get("datum"))
        continuity = entry.get("continuity", {}).get("status")
        if not current:
            current = [index]
        elif continuity == "continuous" and current[-1] == index - 1:
            current.append(index)
        else:
            output.append(current)
            current = [index]
    if current:
        output.append(current)
    return output


def _metric_svg(record: dict[str, Any]) -> str:
    entries = record["entries"]
    values = [_number(entry["value"]["datum"]) for entry in entries if isinstance(entry.get("value"), dict)]
    lo, hi = (min(values), max(values)) if values else (Decimal(0), Decimal(0))

    def y(value: Decimal) -> Decimal:
        if hi == lo:
            return (TOP + BOTTOM) / 2
        return BOTTOM - (value - lo) / (hi - lo) * (BOTTOM - TOP)

    title_id = f"phase15-title-{record['series_id'][:12]}"
    desc_id = f"phase15-desc-{record['series_id'][:12]}"
    segments = _segments(entries)
    segment_for = {index: number for number, segment in enumerate(segments) for index in segment}

    parts = [
        f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="{title_id} {desc_id}" data-visual-mode="numeric" data-segment-count="{len(segments)}">',
        f'<title id="{title_id}">{_esc(PUBLIC_SERIES_KEY)} public temporal evidence</title>',
        f'<desc id="{desc_id}">Twenty-four canonical UTC-hour slots from validated Phase 13 repository evidence. Dashed markers are explicit gaps, squares are degraded-backed values, and lines join only exact Phase 13 continuity.</desc>',
        '<line x1="80" y1="330" x2="930" y2="330" stroke="currentColor"/>',
        '<line x1="80" y1="70" x2="80" y2="330" stroke="currentColor"/>',
        f'<text x="76" y="74" text-anchor="end">max {_esc(format(hi, "f"))}</text>',
        f'<text x="76" y="330" text-anchor="end">min {_esc(format(lo, "f"))}</text>',
        '<text x="80" y="365">Legend: ○ validated value; □ degraded-backed value; ┆ explicit gap; lines require exact continuity</text>',
    ]
    for segment_number, segment in enumerate(segments):
        parts.append(f'<g class="metric-segment" data-segment="{segment_number}">')
        if len(segment) > 1:
            points = [f'{_coord(_x(index, len(entries)))} {_coord(y(_number(entries[index]["value"]["datum"])))}' for index in segment]
            parts.append(f'<path class="metric-line" d="M {" L ".join(points)}" fill="none" stroke="currentColor"/>')
        parts.append("</g>")

    for index, entry in enumerate(entries):
        xpos = _x(index, len(entries))
        xtext = _coord(xpos)
        if entry.get("value") is None:
            reason = entry["gap"]["reason"]
            parts.append(
                f'<g class="gap-marker" data-slot-index="{index}" data-gap-reason="{_esc(reason)}">'
                f'<title>{_esc(entry["slot_utc"])}: {_esc(reason)}</title>'
                f'<line x1="{xtext}" y1="70" x2="{xtext}" y2="330" stroke="currentColor" stroke-dasharray="5 5"/>'
                f'<text x="{xtext}" y="348" text-anchor="middle">gap</text></g>'
            )
            continue
        value = entry["value"]
        ypos = y(_number(value["datum"]))
        title = f'{entry["slot_utc"]}: {_display(value["datum"])}; continuity={entry["continuity"]["status"]}; ' + ("degraded-backed" if _is_degraded(entry) else "validated")
        if _is_degraded(entry):
            parts.append(
                f'<rect class="metric-point degraded" data-slot-index="{index}" data-segment="{segment_for[index]}" x="{_coord(xpos - 4)}" y="{_coord(ypos - 4)}" width="8" height="8"><title>{_esc(title)}</title></rect>'
            )
        else:
            parts.append(
                f'<circle class="metric-point" data-slot-index="{index}" data-segment="{segment_for[index]}" cx="{xtext}" cy="{_coord(ypos)}" r="4"><title>{_esc(title)}</title></circle>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _evidence_table(record: dict[str, Any]) -> str:
    headings = (
        "Slot UTC",
        "State",
        "Exact BTC price USD",
        "Continuity evidence",
        "Comparison status",
        "Comparison ID",
        "Current candidates",
        "Predecessor candidates",
        "Current evidence",
        "Predecessor evidence",
        "Metric evidence",
    )
    rows: list[str] = []
    for entry in record["entries"]:
        value = entry.get("value")
        gap = entry.get("gap")
        comparison = _comparison(entry)
        state = "value" if value is not None else gap["reason"]
        datum = _display(value["datum"]) if value is not None else "—"
        metric_evidence = value.get("evidence") if value is not None else gap.get("metric_evidence")
        cells = (
            entry["slot_utc"],
            state,
            datum,
            _json(entry["continuity"]),
            comparison.get("comparison_status") or "—",
            comparison.get("comparison_id") or "—",
            _json(comparison.get("current_candidates")),
            _json(comparison.get("predecessor_candidates")),
            _json(comparison.get("current")),
            _json(comparison.get("predecessor")),
            _json(metric_evidence),
        )
        rows.append(f'<tr data-slot-utc="{_esc(entry["slot_utc"])}"><th scope="row">{_esc(cells[0])}</th>' + "".join(f"<td>{_esc(cell)}</td>" for cell in cells[1:]) + "</tr>")
    return (
        '<table class="temporal-evidence-table">'
        f"<caption>Complete {PUBLIC_SLOT_COUNT}-slot repository evidence for {_esc(PUBLIC_SERIES_KEY)}</caption>"
        "<thead><tr>"
        + "".join(f'<th scope="col">{_esc(heading)}</th>' for heading in headings)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_validated_public_series(record: dict[str, Any]) -> str:
    """Pure deterministic renderer for an already validated Phase 15-shaped record."""
    svg = _metric_svg(record)
    caption = (
        f'Deterministic repository-bound temporal evidence for {PUBLIC_SERIES_KEY}, from {record["window"]["start_utc"]} through {record["window"]["end_utc"]}. '
        "Every value and gap is reproduced from the validated Phase 13 record. No interpolation, aggregation, smoothing, backfill, inferred trend or generated narrative is introduced."
    )
    return (
        f'<section class="phase15-public-temporal-evidence" data-contract-version="phase15-public-temporal-evidence/v1" data-schema-version="{_esc(record["schema_version"])}" data-series-kind="{_esc(record["series_kind"])}" data-series-key="{_esc(record["series_key"])}" data-series-id="{_esc(record["series_id"])}">'
        "<figure>"
        + svg
        + f"<figcaption>{_esc(caption)}</figcaption></figure>"
        + _evidence_table(record)
        + "</section>\n"
    )


def render_observation_hour_series(repository_root: Path, record: Any) -> str:
    """Replay-validate repository-bound Phase 13 evidence before any rendering."""
    root = Path(repository_root)
    validate_observation_hour_series(root, record)
    shaped = _enforce_public_series_shape(record)
    if shaped.get("series_kind") != PUBLIC_SERIES_KIND or shaped.get("series_key") != PUBLIC_SERIES_KEY:
        raise Phase15PublicTemporalEvidenceError("public renderer series identity mismatch")
    return _render_validated_public_series(shaped)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render one validated Phase 15 BTC.price_usd observation-hour series.")
    parser.add_argument("repository_root")
    parser.add_argument("series_path")
    args = parser.parse_args()
    record = json.loads(Path(args.series_path).read_text(encoding="utf-8"))
    sys.stdout.write(render_observation_hour_series(Path(args.repository_root), record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
