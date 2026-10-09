"""Static-site integration for exactly replay-validated sparse observed prices."""
from __future__ import annotations

import html
import importlib
import math
import sys
from pathlib import Path

from . import temporal_evidence


def _escape(value):
    return html.escape(str(value), quote=True)


def _draw_points(entries, asset):
    points = [(i, row["prices_usd"][asset]) for i, row in enumerate(entries) if row["state"].startswith("OBSERVED")]
    if not points:
        return '<p>No validated observed prices in this window.</p>'
    if any(isinstance(price, bool) or not isinstance(price, (int, float))
           or not math.isfinite(price) or price <= 0 for _, price in points):
        raise ValueError("nonfinite or invalid SVG observation price")
    low = min(p for _, p in points)
    high = max(p for _, p in points)
    span = high - low
    markers = []
    for i, price in points:
        x = 36 + (i * 700 / 23)
        ratio = (price - low) / span if span else 0.5
        y = 175 - (135 * ratio)
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError("nonfinite SVG observation coordinate")
        markers.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="currentColor"><title>{_escape(entries[i]["slot_utc"])}: ${_escape(price)} USD</title></circle>')
    return (
        '<svg viewBox="0 0 780 220" style="display:block;max-width:100%;height:auto" role="img" aria-label="Discrete observed '
        + _escape(asset)
        + ' prices only; intermediate hours are not observed. Refer to the evidence table.">'
        + '<path d="M36 30V175H736" fill="none" stroke="currentColor" opacity=".4"/>'
        + "".join(markers)
        + '</svg>'
    )


def render(repository_root, candidate):
    # This must remain the only entry to render evidence. The replay computes from Git bytes.
    from observed_price_history import validate_replay
    record = validate_replay(Path(repository_root), candidate)
    entries = record["entries"]
    parts = [
        '<section aria-labelledby="observed-history-heading">',
        '<h1 id="observed-history-heading">Observed crypto prices — sparse historical evidence</h1>',
        '<p><strong>Historical prototype demonstration, not live market data or financial advice.</strong> '
        'Data may be stale; archived AI-generated reports may contain errors. No trading recommendations.</p>',
        '<p>Each marker represents a validated snapshot in its canonical UTC observation-hour slot; '
        'the actual collection time is shown in the table. Empty intervals are not interpolated. '
        'Observed prices do not prove hourly price changes, returns or trends.</p>',
        '<p>Period: ' + _escape(record["window"]["start_utc"]) + ' to '
        + _escape(record["window"]["end_utc"]) + '</p>',
    ]
    for asset in record["assets"]:
        parts.append('<section aria-label="' + _escape(asset) + ' observation markers"><h2>' + _escape(asset) + '</h2>')
        parts.append(_draw_points(entries, asset))
        parts.append('</section>')
    parts.append('<h2>Complete hourly evidence and provenance</h2>')
    parts.append('<div class="table-scroll-wrap" role="region" tabindex="0" '
                 'aria-label="Scrollable complete hourly observed price evidence" '
                 'style="max-width:100%;overflow-x:auto">')
    parts.append('<table style="width:100%;min-width:980px;border-collapse:collapse"><caption>All 24 UTC hours, with unavailable data explicitly distinguished</caption>'
                 '<thead><tr><th scope="col">Observation hour (UTC)</th><th scope="col">Evidence state</th>'
                 '<th scope="col">BTC USD</th><th scope="col">ETH USD</th><th scope="col">SOL USD</th>'
                 '<th scope="col">Actual generated (UTC)</th><th scope="col">Committed snapshot</th></tr></thead><tbody>')
    for row in entries:
        def price(asset):
            value = row["prices_usd"][asset]
            return _escape(value) if value is not None else "Unavailable"
        candidate = row["candidates"][0] if len(row["candidates"]) == 1 else None
        provenance = "No qualifying snapshot"
        generated = "Unavailable"
        if candidate:
            generated = _escape(candidate["generated_at_utc"] or "Unavailable")
            provenance = (
                '<code style="overflow-wrap:anywhere">' + _escape(candidate["path"]) + '</code>'
                '<details><summary>Source hashes</summary><code>Git blob '
                + _escape(candidate["git_blob_sha"])
                + '</code> <code>SHA-256 ' + _escape(candidate["snapshot_sha256"]) + '</code></details>'
            )
        elif row["state"] == "AMBIGUOUS":
            provenance = "Multiple source candidates — no winner selected"
        message = row["state"] + (": " + row["blocked_reason"] if row["blocked_reason"] else "")
        if row["warnings"]:
            message += " (warnings: " + ", ".join(map(str, row["warnings"])) + ")"
        parts.append(
            '<tr><th scope="row">' + _escape(row["slot_utc"]) + '</th>'
            '<td>' + _escape(message) + '</td><td>' + price("BTC") + '</td>'
            '<td>' + price("ETH") + '</td><td>' + price("SOL") + '</td>'
            '<td>' + generated + '</td><td>' + provenance + '</td></tr>'
        )
    parts.append('</tbody></table></div>')
    parts.append('<p>Immutable source commit: <code>' + _escape(record["repository_context"]["commit_sha"]) + '</code>; '
                 'tree: <code>' + _escape(record["repository_context"]["tree_sha"]) + '</code>; '
                 'record ID: <code>' + _escape(record["record_id"]) + '</code>.</p></section>')
    return "\n".join(parts)


def apply(base):
    root = Path(base.ROOT)
    out = Path(base.OUT)
    page = out / "observed-prices.html"
    index = out / "index.html"
    page.unlink(missing_ok=True)
    if not index.is_file():
        raise ValueError("site index missing")
    commit = temporal_evidence.resolve_checkout_commit(root)
    from observed_price_history import materialise
    candidate = materialise(root, commit)
    evidence = render(root, candidate)
    source = (
        '<!doctype html><html lang="en-AU"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Observed prices | CryptoPulse</title>'
        '<link rel="stylesheet" href="assets/cryptopulse.css"></head><body>'
        '<main class="page"><article class="brief">'
        + base.demo_banner() + evidence + base.footer() + '</article></main></body></html>'
    )
    index_html = index.read_text(encoding="utf-8")
    if "</main>" not in index_html or 'href="observed-prices.html"' in index_html:
        raise ValueError("site discovery insertion ambiguous")
    new_index = index_html.replace(
        "</main>",
        '<nav aria-label="Observed price evidence"><a href="observed-prices.html">Explore sparse historical observed prices</a></nav></main>',
        1,
    )
    # Only write after all authority, reconstruction and page validation has succeeded.
    page.write_text(source, encoding="utf-8")
    index.write_text(new_index, encoding="utf-8")
    return True
