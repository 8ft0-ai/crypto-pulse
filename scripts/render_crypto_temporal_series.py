#!/usr/bin/env python3
"""Render validated Phase 11 temporal series as deterministic accessible HTML/SVG."""
from __future__ import annotations

import argparse, html, json, math, sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from crypto_temporal_series import TemporalSeriesError, validate_temporal_series

WIDTH, HEIGHT = 960, 420
LEFT, RIGHT, TOP, BOTTOM = map(Decimal, ("80", "930", "70", "330"))
Q = Decimal("0.01")


def esc(v: Any) -> str:
    return html.escape(str(v), quote=True)


def coord(v: Decimal) -> str:
    s = format(v.quantize(Q, rounding=ROUND_HALF_UP), "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def xpos(i: int, n: int) -> Decimal:
    return (LEFT + RIGHT) / 2 if n <= 1 else LEFT + (RIGHT - LEFT) * Decimal(i) / Decimal(n - 1)


def number(v: Any) -> Decimal:
    if isinstance(v, bool) or v is None or not isinstance(v, (int, float, str)):
        raise TemporalSeriesError("validated metric datum must be numeric")
    if isinstance(v, float) and not math.isfinite(v):
        raise TemporalSeriesError("validated metric datum must be finite")
    try:
        out = Decimal(str(v).strip())
    except (InvalidOperation, ValueError) as exc:
        raise TemporalSeriesError("validated metric datum must be numeric") from exc
    if not out.is_finite():
        raise TemporalSeriesError("validated metric datum must be finite")
    return out


def display(v: Any) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def side(entry: dict[str, Any], name: str) -> Any:
    payload = entry["value"] if entry.get("value") is not None else entry["gap"]
    return payload.get(name) if isinstance(payload, dict) else None


def warnings(v: Any) -> str:
    if v is None:
        return "—"
    items = v.get("non_blocking_warnings") if isinstance(v, dict) else None
    if items is None:
        return "—"
    if not isinstance(items, list):
        raise TemporalSeriesError("validated warnings must be a list")
    return "none" if not items else "; ".join(str(x) for x in items)


def quality(v: Any) -> str:
    return str(v.get("quality_status")) if isinstance(v, dict) and v.get("quality_status") is not None else "—"


def provenance(v: Any) -> str:
    if not isinstance(v, dict):
        return "—"
    return "; ".join(
        f"{k}={v.get(src)}"
        for k, src in (("path", "path"), ("sha256", "sha256"), ("schema", "schema_version"), ("generated_at_utc", "generated_at_utc"))
    )


def evidence(entry: dict[str, Any]) -> str:
    if entry.get("value") is not None:
        obj = entry["value"].get("evidence")
        return "—" if obj is None else json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    gap = entry["gap"]
    if gap.get("reason") == "current-ambiguous":
        return " | ".join(
            f"path={c.get('path')}; sha256={c.get('sha256')}; schema={c.get('schema_version')}; generated_at_utc={c.get('generated_at_utc')}"
            for c in gap.get("current_candidates", [])
        )
    detail = {k: v for k, v in gap.items() if k not in {"current", "predecessor"}}
    return json.dumps(detail, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) if detail else "—"


def degraded(v: dict[str, Any]) -> bool:
    return any(isinstance(v.get(k), dict) and v[k].get("quality_status") == "valid-degraded" for k in ("current", "predecessor"))


def segments(entries: list[dict[str, Any]]) -> list[list[int]]:
    out, current = [], []
    for i, e in enumerate(entries):
        v = e.get("value")
        if not isinstance(v, dict):
            if current: out.append(current); current = []
            continue
        number(v.get("datum"))
        if not current:
            current = [i]; continue
        prev = entries[current[-1]]["value"]
        if v.get("predecessor") == prev.get("current"):
            current.append(i)
        else:
            out.append(current); current = [i]
    if current: out.append(current)
    return out


def metric_svg(record: dict[str, Any], title_id: str, desc_id: str) -> str:
    entries = record["entries"]
    nums = [number(e["value"]["datum"]) for e in entries if isinstance(e.get("value"), dict)]
    lo, hi = (min(nums), max(nums)) if nums else (Decimal(0), Decimal(0))
    def ypos(v: Decimal) -> Decimal:
        return (TOP + BOTTOM) / 2 if hi == lo else BOTTOM - (v - lo) / (hi - lo) * (BOTTOM - TOP)
    segs = segments(entries)
    seg_for = {i: s for s, seg in enumerate(segs) for i in seg}
    b = [
        f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="{title_id} {desc_id}" data-visual-mode="numeric" data-segment-count="{len(segs)}">',
        f'<title id="{title_id}">{esc(record["series_key"])} temporal evidence</title>',
        f'<desc id="{desc_id}">Validated hourly Phase 10 evidence. Dashed markers are gaps; squares are degraded-backed points. Lines connect only exact predecessor/current identity continuity.</desc>',
        '<line x1="80" y1="330" x2="930" y2="330" stroke="currentColor"/><line x1="80" y1="70" x2="80" y2="330" stroke="currentColor"/>',
        f'<text x="76" y="74" text-anchor="end">max {esc(format(hi,"f"))}</text><text x="76" y="330" text-anchor="end">min {esc(format(lo,"f"))}</text>',
        '<text x="80" y="365">Legend: ○ valid-ok-backed; □ degraded-backed; ┆ explicit gap</text>',
    ]
    for s, seg in enumerate(segs):
        b.append(f'<g class="metric-segment" data-segment="{s}">')
        if len(seg) > 1:
            pts = [f'{coord(xpos(i,len(entries)))} {coord(ypos(number(entries[i]["value"]["datum"])))}' for i in seg]
            b.append(f'<path class="metric-line" d="M {" L ".join(pts)}" fill="none" stroke="currentColor"/>')
        b.append('</g>')
    for i, e in enumerate(entries):
        x = coord(xpos(i, len(entries)))
        if e.get("value") is None:
            b.append(f'<g class="gap-marker" data-slot-index="{i}"><title>{esc(e["slot_utc"])}: {esc(e["gap"]["reason"])}</title><line x1="{x}" y1="70" x2="{x}" y2="330" stroke="currentColor" stroke-dasharray="5 5"/><text x="{x}" y="348" text-anchor="middle">gap</text></g>')
            continue
        v, y = e["value"], coord(ypos(number(e["value"]["datum"])))
        title = esc(f'{e["slot_utc"]}: {display(v["datum"])}; ' + ("degraded-backed" if degraded(v) else "valid-ok-backed"))
        if degraded(v):
            b.append(f'<rect class="metric-point degraded" data-slot-index="{i}" data-segment="{seg_for[i]}" x="{coord(Decimal(x)-4)}" y="{coord(Decimal(y)-4)}" width="8" height="8"><title>{title}</title></rect>')
        else:
            b.append(f'<circle class="metric-point" data-slot-index="{i}" data-segment="{seg_for[i]}" cx="{x}" cy="{y}" r="4"><title>{title}</title></circle>')
    b.append('</svg>')
    return "".join(b)


def source_marker(status: str, x: Decimal, y: Decimal) -> str:
    X, Y = coord(x), coord(y)
    if status == "ok": return f'<circle cx="{X}" cy="{Y}" r="6"/>'
    if status == "warning": return f'<polygon points="{X},{coord(y-7)} {coord(x-7)},{coord(y+6)} {coord(x+7)},{coord(y+6)}"/>'
    if status == "error": return f'<path d="M {coord(x-6)} {coord(y-6)} L {coord(x+6)} {coord(y+6)} M {coord(x+6)} {coord(y-6)} L {coord(x-6)} {coord(y+6)}"/>'
    if status == "skipped": return f'<rect x="{coord(x-6)}" y="{coord(y-6)}" width="12" height="12"/>'
    if status == "missing": return f'<polygon points="{X},{coord(y-7)} {coord(x-7)},{Y} {X},{coord(y+7)} {coord(x+7)},{Y}"/>'
    raise TemporalSeriesError(f"unsupported validated source status: {status!r}")


def source_svg(record: dict[str, Any], title_id: str, desc_id: str) -> str:
    entries, y = record["entries"], Decimal(190)
    b = [
        f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="{title_id} {desc_id}" data-visual-mode="categorical">',
        f'<title id="{title_id}">{esc(record["series_key"])} source-status history</title>',
        f'<desc id="{desc_id}">Categorical source-status timeline with text and distinct marker shapes. Gaps are dashed. No numeric market axis is used.</desc>',
        '<line x1="80" y1="190" x2="930" y2="190" stroke="currentColor"/><text x="80" y="70">Categorical source-status timeline — no numeric market axis</text>',
        '<text x="80" y="365">Legend: ○ ok; △ warning; × error; □ skipped; ◇ missing; ┆ explicit gap</text>',
    ]
    for i, e in enumerate(entries):
        x = xpos(i, len(entries)); X = coord(x)
        if e.get("value") is None:
            b.append(f'<g class="gap-marker" data-slot-index="{i}"><title>{esc(e["slot_utc"])}: {esc(e["gap"]["reason"])}</title><line x1="{X}" y1="120" x2="{X}" y2="260" stroke="currentColor" stroke-dasharray="5 5"/><text x="{X}" y="282" text-anchor="middle">gap</text></g>')
        else:
            status = e["value"]["datum"]
            if not isinstance(status, str): raise TemporalSeriesError("validated source-status datum must be a string")
            b.append(f'<g class="source-status-marker" data-slot-index="{i}" data-status="{esc(status)}" fill="none" stroke="currentColor">{source_marker(status,x,y)}</g><text x="{X}" y="218" text-anchor="middle">{esc(status)}</text>')
    b.append('</svg>')
    return "".join(b)


def table(record: dict[str, Any]) -> str:
    rows = []
    for e in record["entries"]:
        v = e.get("value"); g = e.get("gap")
        state, exact = ("value", display(v["datum"])) if v is not None else (g["reason"], "—")
        cur, pred = side(e,"current"), side(e,"predecessor")
        payload = v if v is not None else g
        cells = [e["slot_utc"], state, exact, quality(cur), warnings(cur), quality(pred), warnings(pred), payload.get("comparison_id") or "—", provenance(cur), provenance(pred), evidence(e)]
        rows.append(f'<tr data-slot-utc="{esc(e["slot_utc"])}"><th scope="row">{esc(cells[0])}</th>' + ''.join(f'<td>{esc(x)}</td>' for x in cells[1:]) + '</tr>')
    heads = ("Slot UTC","State","Exact value/status","Current quality","Current warnings","Predecessor quality","Predecessor warnings","Comparison ID","Current provenance","Predecessor provenance","Evidence detail")
    return f'<table class="temporal-evidence-table"><caption>Complete hourly evidence for {esc(record["series_key"])}</caption><thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in heads) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


def _render_validated_series(record: dict[str, Any]) -> str:
    sid = record["series_id"]; tid, did = f"series-title-{sid[:12]}", f"series-desc-{sid[:12]}"
    svg = metric_svg(record,tid,did) if record["series_kind"] == "metric" else source_svg(record,tid,did)
    title = f'{record["series_key"]} — {record["window"]["start_utc"]} to {record["window"]["end_utc"]}'
    caption = f'Deterministic offline temporal evidence for {record["series_key"]} from {record["window"]["start_utc"]} through {record["window"]["end_utc"]}. Values and statuses come only from the validated canonical Phase 11 record; gaps remain explicit and no interpolation, aggregation, smoothing, normalisation, backfill or inferred value is introduced.'
    style = 'body{font-family:system-ui,sans-serif;margin:1rem;line-height:1.4}figure{margin:0 0 1rem;overflow-x:auto}svg{max-width:100%;height:auto;border:1px solid currentColor}table{border-collapse:collapse;width:100%;font-size:.85rem}th,td{border:1px solid currentColor;padding:.35rem;vertical-align:top;text-align:left}.temporal-evidence-table td:nth-child(n+8){font-family:ui-monospace,monospace;word-break:break-all}caption{font-weight:700;text-align:left;margin:.5rem 0}'
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title><style>{style}</style></head><body><main data-schema-version="{esc(record["schema_version"])}" data-series-kind="{esc(record["series_kind"])}" data-series-id="{esc(sid)}"><figure>{svg}<figcaption>{esc(caption)}</figcaption></figure>{table(record)}</main></body></html>\n'


def render_temporal_series(repository_root: Path, record: Any) -> str:
    """Validate repository-bound evidence before producing renderer output."""
    validate_temporal_series(Path(repository_root), record)
    if not isinstance(record, dict): raise TemporalSeriesError("validated series must be an object")
    return _render_validated_series(record)


def main() -> int:
    p = argparse.ArgumentParser(description="Render one validated crypto-temporal-series/v1 record.")
    p.add_argument("repository_root"); p.add_argument("series_path")
    a = p.parse_args(); record = json.loads(Path(a.series_path).read_text(encoding="utf-8"))
    sys.stdout.write(render_temporal_series(Path(a.repository_root), record)); return 0


if __name__ == "__main__": raise SystemExit(main())
