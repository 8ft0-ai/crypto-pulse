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


def _number_for_series(value: Any, series_key: str) -> Decimal:
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
    if result <= 0:
        raise Phase15PublicTemporalEvidenceError(
            f"validated {series_key} datum must be strictly positive"
        )
    return result


def _number(value: Any) -> Decimal:
    return _number_for_series(value, PUBLIC_SERIES_KEY)


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


def _segments_for_series(
    entries: list[dict[str, Any]],
    series_key: str,
) -> list[list[int]]:
    """Group asserted values without ever bridging a gap or discontinuity."""
    output: list[list[int]] = []
    current: list[int] = []
    for index, entry in enumerate(entries):
        if entry.get("value") is None:
            if current:
                output.append(current)
                current = []
            continue
        _number_for_series(entry["value"].get("datum"), series_key)
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


def _segments(entries: list[dict[str, Any]]) -> list[list[int]]:
    return _segments_for_series(entries, PUBLIC_SERIES_KEY)


def _reader_projection_for_series(
    record: dict[str, Any],
    series_key: str,
) -> dict[str, Any]:
    """Project reader summary state from one already validated 24-slot record."""
    if record.get("series_key") != series_key:
        raise Phase15PublicTemporalEvidenceError("reader projection series identity mismatch")

    entries = record["entries"]
    value_count = 0
    degraded_value_count = 0
    continuous_pair_count = 0
    longest_continuous_run = 0
    current_run = 0
    gap_reasons: dict[str, int] = {}

    for index, entry in enumerate(entries):
        value = entry.get("value")
        if isinstance(value, dict):
            _number_for_series(value.get("datum"), series_key)
            value_count += 1
            if _is_degraded(entry):
                degraded_value_count += 1

            previous_is_value = (
                index > 0 and isinstance(entries[index - 1].get("value"), dict)
            )
            if (
                previous_is_value
                and entry.get("continuity", {}).get("status") == "continuous"
            ):
                continuous_pair_count += 1
                current_run = current_run + 1 if current_run else 2
            else:
                current_run = 1
            longest_continuous_run = max(longest_continuous_run, current_run)
            continue

        gap = entry.get("gap")
        reason = gap.get("reason") if isinstance(gap, dict) else None
        if not isinstance(reason, str) or not reason:
            raise Phase15PublicTemporalEvidenceError(
                "validated gap must retain an exact reason"
            )
        gap_reasons[reason] = gap_reasons.get(reason, 0) + 1
        current_run = 0

    gap_count = PUBLIC_SLOT_COUNT - value_count
    if gap_count != sum(gap_reasons.values()):
        raise Phase15PublicTemporalEvidenceError(
            "reader projection gap count does not match retained evidence"
        )

    return {
        "value_count": value_count,
        "gap_count": gap_count,
        "gap_reasons": dict(sorted(gap_reasons.items())),
        "degraded_value_count": degraded_value_count,
        "continuous_pair_count": continuous_pair_count,
        "longest_continuous_run": longest_continuous_run,
    }


def _reader_projection(record: dict[str, Any]) -> dict[str, Any]:
    """Project reader summary state from the already validated 24-slot record."""
    return _reader_projection_for_series(record, PUBLIC_SERIES_KEY)


def _metric_svg_for_series(
    record: dict[str, Any],
    projection: dict[str, Any],
    series_key: str,
    *,
    title_id_prefix: str,
    title_text: str,
) -> str:
    entries = record["entries"]
    values = [
        _number_for_series(entry["value"]["datum"], series_key)
        for entry in entries
        if isinstance(entry.get("value"), dict)
    ]
    if not values:
        return ""

    lo, hi = min(values), max(values)

    def y(value: Decimal) -> Decimal:
        if hi == lo:
            return (TOP + BOTTOM) / 2
        return BOTTOM - (value - lo) / (hi - lo) * (BOTTOM - TOP)

    title_id = f"{title_id_prefix}-title-{record['series_id'][:12]}"
    desc_id = f"{title_id_prefix}-desc-{record['series_id'][:12]}"
    segments = _segments_for_series(entries, series_key)
    segment_for = {
        index: number for number, segment in enumerate(segments) for index in segment
    }
    visual_mode = "line" if projection["continuous_pair_count"] > 0 else "points"

    parts = [
        f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="{title_id} {desc_id}" data-visual-mode="{visual_mode}" data-segment-count="{len(segments)}">',
        f'<title id="{title_id}">{_esc(title_text)}</title>',
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
            points = [
                f'{_coord(_x(index, len(entries)))} {_coord(y(_number_for_series(entries[index]["value"]["datum"], series_key)))}'
                for index in segment
            ]
            parts.append(
                f'<path class="metric-line" d="M {" L ".join(points)}" fill="none" stroke="currentColor"/>'
            )
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
        ypos = y(_number_for_series(value["datum"], series_key))
        title = (
            f'{entry["slot_utc"]}: {_display(value["datum"])}; '
            f'continuity={entry["continuity"]["status"]}; '
            + ("degraded-backed" if _is_degraded(entry) else "validated")
        )
        if _is_degraded(entry):
            parts.append(
                f'<rect class="metric-point degraded" data-slot-index="{index}" '
                f'data-segment="{segment_for[index]}" x="{_coord(xpos - 4)}" '
                f'y="{_coord(ypos - 4)}" width="8" height="8">'
                f'<title>{_esc(title)}</title></rect>'
            )
        else:
            parts.append(
                f'<circle class="metric-point" data-slot-index="{index}" '
                f'data-segment="{segment_for[index]}" cx="{xtext}" '
                f'cy="{_coord(ypos)}" r="4"><title>{_esc(title)}</title></circle>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _metric_svg(record: dict[str, Any], projection: dict[str, Any]) -> str:
    return _metric_svg_for_series(
        record,
        projection,
        PUBLIC_SERIES_KEY,
        title_id_prefix="phase15",
        title_text=f"{PUBLIC_SERIES_KEY} public temporal evidence",
    )


def _reader_summary_for_series(
    projection: dict[str, Any],
    series_key: str,
) -> str:
    gap_reasons = projection["gap_reasons"]
    if gap_reasons:
        gap_html = "".join(
            f'<li data-gap-reason="{_esc(reason)}"><code>{_esc(reason)}</code><span>{count}</span></li>'
            for reason, count in gap_reasons.items()
        )
    else:
        gap_html = "<li><span>No retained gaps in this window.</span></li>"

    if projection["value_count"] == 0:
        chart_note = (
            f"No asserted {series_key} values exist in this 24-slot record, "
            "so no chart or numeric extrema are rendered."
        )
    elif projection["continuous_pair_count"] == 0:
        chart_note = (
            "Asserted values are isolated by retained continuity evidence; "
            "points may be shown, but no connecting line is rendered."
        )
    else:
        chart_note = (
            "Lines are drawn only across exact adjacent asserted values whose "
            "retained continuity status is continuous."
        )

    return f"""
<div class="temporal-reader-summary" aria-label="Temporal evidence reader summary"
     data-value-count="{projection["value_count"]}"
     data-gap-count="{projection["gap_count"]}"
     data-degraded-value-count="{projection["degraded_value_count"]}"
     data-continuous-pair-count="{projection["continuous_pair_count"]}"
     data-longest-continuous-run="{projection["longest_continuous_run"]}">
  <div class="eyebrow">24-slot evidence coverage</div>
  <h2>What this repository window contains</h2>
  <dl class="temporal-reader-metrics">
    <div><dt>Asserted values</dt><dd>{projection["value_count"]}</dd></div>
    <div><dt>Explicit gaps</dt><dd>{projection["gap_count"]}</dd></div>
    <div><dt>Degraded-backed values</dt><dd>{projection["degraded_value_count"]}</dd></div>
    <div><dt>Continuous pairs</dt><dd>{projection["continuous_pair_count"]}</dd></div>
    <div><dt>Longest continuous run</dt><dd>{projection["longest_continuous_run"]}</dd></div>
  </dl>
  <div class="temporal-gap-summary">
    <h3>Exact retained gap reasons</h3>
    <ul>{gap_html}</ul>
  </div>
  <p class="temporal-chart-note">{_esc(chart_note)}</p>
</div>
"""


def _reader_summary(projection: dict[str, Any]) -> str:
    return _reader_summary_for_series(projection, PUBLIC_SERIES_KEY)


def _evidence_table_for_series(
    record: dict[str, Any],
    series_key: str,
    value_column_label: str,
) -> str:
    if record.get("series_key") != series_key:
        raise Phase15PublicTemporalEvidenceError("evidence table series identity mismatch")

    headings = (
        "Slot UTC",
        "State",
        value_column_label,
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
        rows.append(
            f'<tr data-slot-utc="{_esc(entry["slot_utc"])}"><th scope="row">{_esc(cells[0])}</th>'
            + "".join(f"<td>{_esc(cell)}</td>" for cell in cells[1:])
            + "</tr>"
        )
    return (
        '<div class="temporal-evidence-table-wrap">'
        '<table class="temporal-evidence-table">'
        f"<caption>Complete {PUBLIC_SLOT_COUNT}-slot repository evidence for {_esc(series_key)}</caption>"
        "<thead><tr>"
        + "".join(f'<th scope="col">{_esc(heading)}</th>' for heading in headings)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _evidence_table(record: dict[str, Any]) -> str:
    return _evidence_table_for_series(
        record,
        PUBLIC_SERIES_KEY,
        "Exact BTC price USD",
    )


def _render_validated_price_series(
    record: dict[str, Any],
    series_key: str,
    *,
    title_id_prefix: str,
    chart_title: str,
    value_column_label: str,
    section_class: str,
    contract_version: str,
) -> str:
    projection = _reader_projection_for_series(record, series_key)
    svg = _metric_svg_for_series(
        record,
        projection,
        series_key,
        title_id_prefix=title_id_prefix,
        title_text=chart_title,
    )
    caption = (
        f"Deterministic repository-bound temporal evidence for {series_key}, "
        f'from {record["window"]["start_utc"]} through {record["window"]["end_utc"]}. '
        "Every value and gap is reproduced from the validated Phase 13 record. "
        "No interpolation, aggregation, smoothing, backfill, carry-forward, gap bridging, "
        "inferred trend or generated narrative is introduced."
    )
    figure = (
        '<figure class="temporal-evidence-visual">'
        + svg
        + f"<figcaption>{_esc(caption)}</figcaption></figure>"
        if svg
        else ""
    )
    empty_state = (
        '<div class="temporal-empty-state" role="status">'
        f"No asserted {series_key} values are available in this validated 24-slot repository window. "
        "All retained gap evidence remains inspectable below."
        "</div>"
        if projection["value_count"] == 0
        else ""
    )
    return (
        f'<section class="{_esc(section_class)}" '
        f'data-contract-version="{_esc(contract_version)}" '
        f'data-schema-version="{_esc(record["schema_version"])}" '
        f'data-series-kind="{_esc(record["series_kind"])}" '
        f'data-series-key="{_esc(record["series_key"])}" '
        f'data-series-id="{_esc(record["series_id"])}">'
        + _reader_summary_for_series(projection, series_key)
        + empty_state
        + figure
        + '<section class="temporal-evidence-inspect" aria-label="Inspect the temporal evidence">'
        + "<h2>Inspect the evidence</h2>"
        + "<p>The complete validated 24-slot record remains available below, including exact gaps, continuity and repository evidence identities.</p>"
        + _evidence_table_for_series(record, series_key, value_column_label)
        + "</section>"
        + "</section>\n"
    )


def _render_validated_public_series(record: dict[str, Any]) -> str:
    """Pure deterministic renderer for an already validated Phase 15-shaped record."""
    return _render_validated_price_series(
        record,
        PUBLIC_SERIES_KEY,
        title_id_prefix="phase15",
        chart_title=f"{PUBLIC_SERIES_KEY} public temporal evidence",
        value_column_label="Exact BTC price USD",
        section_class="phase15-public-temporal-evidence",
        contract_version="phase15-public-temporal-evidence/v1",
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
