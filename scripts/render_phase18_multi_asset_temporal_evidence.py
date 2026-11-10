#!/usr/bin/env python3
"""Render validated Phase 18 BTC/ETH/SOL temporal evidence without site integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase18_multi_asset_temporal_evidence import (
    PHASE18_CONTRACT_VERSION,
    PUBLIC_SERIES_KEYS,
    Phase18MultiAssetTemporalEvidenceError,
    validate_multi_asset_temporal_evidence,
)
from render_crypto_observation_hour_series import (
    _display,
    _esc,
    _evidence_table_for_series,
    _is_degraded,
    _metric_svg_for_series,
    _reader_projection_for_series,
)

SERIES_PRESENTATION = {
    "BTC.price_usd": {
        "symbol": "BTC",
        "evidence_label": "BTC price evidence",
        "value_column_label": "Exact BTC price USD",
        "svg_id_prefix": "phase18-btc",
    },
    "ETH.price_usd": {
        "symbol": "ETH",
        "evidence_label": "ETH price evidence",
        "value_column_label": "Exact ETH price USD",
        "svg_id_prefix": "phase18-eth",
    },
    "SOL.price_usd": {
        "symbol": "SOL",
        "evidence_label": "SOL price evidence",
        "value_column_label": "Exact SOL price USD",
        "svg_id_prefix": "phase18-sol",
    },
}


def _presentation(series_key: str) -> dict[str, str]:
    presentation = SERIES_PRESENTATION.get(series_key)
    if presentation is None:
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 18 renderer series identity mismatch"
        )
    return presentation


def _reader_state(projection: dict[str, Any]) -> str:
    if projection["value_count"] == 0:
        return "no-asserted-values"
    if projection["continuous_pair_count"] == 0:
        return "asserted-values-no-continuous-pair"
    return "continuous-evidence-available"


def _window_end_value(member: dict[str, Any]) -> tuple[str, bool]:
    final_entry = member["entries"][-1]
    value = final_entry.get("value")
    if isinstance(value, dict):
        return _display(value["datum"]), _is_degraded(final_entry)
    return "Unavailable at window end", False


def _asset_card(
    member: dict[str, Any],
    projection: dict[str, Any],
    window_end: str,
) -> str:
    series_key = member["series_key"]
    presentation = _presentation(series_key)
    value_text, end_degraded = _window_end_value(member)
    degraded = projection["degraded_value_count"]
    degraded_html = (
        f'<div class="phase18-card-degraded"><dt>Degraded-backed asserted values</dt><dd>{degraded}</dd></div>'
        if degraded
        else ""
    )
    end_state = "degraded-backed" if end_degraded else (
        "asserted" if value_text != "Unavailable at window end" else "unavailable"
    )
    return (
        f'<article class="phase18-asset-card" data-series-key="{_esc(series_key)}" '
        f'data-reader-state="{_esc(_reader_state(projection))}">'
        f'<h3>{_esc(presentation["symbol"])}</h3>'
        '<dl class="phase18-card-evidence">'
        f'<div><dt>Window end</dt><dd>{_esc(window_end)}</dd></div>'
        f'<div><dt>Exact window-end evidence</dt><dd data-evidence-state="{end_state}">{_esc(value_text)}</dd></div>'
        f'<div><dt>Asserted-value coverage</dt><dd>{projection["value_count"]} / 24</dd></div>'
        + degraded_html
        + "</dl>"
        + "</article>"
    )


def _asset_chart(
    member: dict[str, Any],
    projection: dict[str, Any],
) -> str:
    series_key = member["series_key"]
    presentation = _presentation(series_key)
    svg = _metric_svg_for_series(
        member,
        projection,
        series_key,
        title_id_prefix=presentation["svg_id_prefix"],
        title_text=presentation["evidence_label"],
    )
    if not svg:
        return (
            f'<section class="phase18-asset-chart" data-series-key="{_esc(series_key)}" '
            'data-chart-state="no-asserted-values">'
            f'<h3>{_esc(presentation["evidence_label"])}</h3>'
            "<p>No asserted values exist for this asset in the validated 24-slot window, so no SVG or numeric extrema are rendered.</p>"
            "</section>"
        )
    chart_state = (
        "continuous-segments"
        if projection["continuous_pair_count"] > 0
        else "points-only"
    )
    caption = (
        f'{presentation["evidence_label"]} for the validated 24-slot repository window. '
        "Every point and retained gap is exact evidence; connecting lines require exact adjacent continuity."
    )
    return (
        f'<section class="phase18-asset-chart" data-series-key="{_esc(series_key)}" '
        f'data-chart-state="{chart_state}">'
        f'<h3>{_esc(presentation["evidence_label"])}</h3>'
        '<figure class="temporal-evidence-visual">'
        + svg
        + f"<figcaption>{_esc(caption)}</figcaption></figure>"
        + "</section>"
    )


def _compact_cell(entry: dict[str, Any]) -> str:
    value = entry.get("value")
    if isinstance(value, dict):
        degraded = _is_degraded(entry)
        state = "degraded-backed" if degraded else "asserted"
        suffix = ' <span class="phase18-degraded-marker">degraded-backed</span>' if degraded else ""
        return (
            f'<td data-evidence-state="{state}">'
            f'{_esc(_display(value["datum"]))}{suffix}</td>'
        )
    gap = entry.get("gap")
    reason = gap.get("reason") if isinstance(gap, dict) else None
    if not isinstance(reason, str) or not reason:
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 18 renderer gap reason is unavailable"
        )
    return (
        '<td data-evidence-state="unavailable">'
        f'Unavailable — <code>{_esc(reason)}</code></td>'
    )


def _compact_table(members: list[dict[str, Any]]) -> str:
    slot_vectors = [[entry["slot_utc"] for entry in member["entries"]] for member in members]
    if not slot_vectors or any(slots != slot_vectors[0] for slots in slot_vectors[1:]):
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 18 renderer slot alignment mismatch"
        )
    rows: list[str] = []
    for index, slot in enumerate(slot_vectors[0]):
        cells = "".join(_compact_cell(member["entries"][index]) for member in members)
        rows.append(
            f'<tr data-slot-utc="{_esc(slot)}"><th scope="row">{_esc(slot)}</th>{cells}</tr>'
        )
    return (
        '<table class="phase18-primary-evidence-table">'
        "<caption>Exact BTC, ETH and SOL evidence across the common 24-slot UTC window</caption>"
        "<thead><tr>"
        '<th scope="col">Slot UTC</th>'
        '<th scope="col">BTC</th>'
        '<th scope="col">ETH</th>'
        '<th scope="col">SOL</th>'
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _audit_details(member: dict[str, Any]) -> str:
    series_key = member["series_key"]
    presentation = _presentation(series_key)
    return (
        f'<details class="phase18-asset-audit" data-series-key="{_esc(series_key)}">'
        f'<summary>Inspect {_esc(presentation["symbol"])} complete evidence</summary>'
        + _evidence_table_for_series(
            member,
            series_key,
            presentation["value_column_label"],
        )
        + "</details>"
    )


def _render_validated_multi_asset_temporal_evidence(bundle: dict[str, Any]) -> str:
    members = bundle["series"]
    if [member.get("series_key") for member in members] != list(PUBLIC_SERIES_KEYS):
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 18 renderer member identity/order mismatch"
        )
    if len(members) != 3:
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 18 renderer requires exactly three members"
        )

    projections = [
        _reader_projection_for_series(member, series_key)
        for member, series_key in zip(members, PUBLIC_SERIES_KEYS)
    ]
    window = bundle["window"]
    window_end = window["end_utc"]

    cards = "".join(
        _asset_card(member, projection, window_end)
        for member, projection in zip(members, projections)
    )
    charts = "".join(
        _asset_chart(member, projection)
        for member, projection in zip(members, projections)
    )
    audits = "".join(_audit_details(member) for member in members)

    return (
        '<section class="phase18-multi-asset-temporal-evidence" '
        f'data-contract-version="{_esc(PHASE18_CONTRACT_VERSION)}" '
        f'data-bundle-id="{_esc(bundle["bundle_id"])}">'
        "<h2>Asset price evidence</h2>"
        f'<p class="phase18-common-window">Common 24-slot UTC window: '
        f'{_esc(window["start_utc"])} through {_esc(window_end)}</p>'
        '<section class="phase18-asset-cards" aria-label="Asset evidence cards">'
        + cards
        + "</section>"
        + '<section class="phase18-asset-charts" aria-label="Independent asset evidence charts">'
        + charts
        + "</section>"
        + '<section class="phase18-primary-table" aria-label="Exact common-window evidence">'
        + "<h3>Common-window evidence</h3>"
        + _compact_table(members)
        + "</section>"
        + '<section class="phase18-audit-evidence" aria-label="Complete per-asset evidence">'
        + "<h3>Complete audit evidence</h3>"
        + audits
        + "</section>"
        + "</section>\n"
    )


def render_multi_asset_temporal_evidence(
    repository_root: Path,
    bundle: Any,
) -> str:
    """Replay-validate the exact Phase 18 bundle before projection or rendering."""
    validated = validate_multi_asset_temporal_evidence(Path(repository_root), bundle)
    return _render_validated_multi_asset_temporal_evidence(validated)
