"""Reader-facing Phase 16 authority projection for Home and Most recent."""

from __future__ import annotations

import hashlib
import html
import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

STYLE_NAME = "cryptopulse-reader-evidence.css"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
HOME_HERO_RE = re.compile(r'(<header class="[^"]*\blanding-hero\b[^"]*">.*?</header>)', re.DOTALL)
LATEST_HERO_RE = re.compile(r'(<header class="[^"]*\breport-hero\b[^"]*">.*?</header>)', re.DOTALL)
LATEST_MARKET_READ_RE = re.compile(r'\s*<section class="latest-market-read".*?</section>\s*', re.DOTALL)
LATEST_FEATURE_RE = re.compile(r'\s*<section class="latest-feature">.*?</section>\s*', re.DOTALL)
HERO_ACTIONS_RE = re.compile(r'\s*<div class="hero-actions".*?</div>\s*', re.DOTALL)


class ReaderEvidenceIntegrationError(ValueError):
    """Raised when Phase 16 cannot safely project reader evidence."""


def _git(repository_root: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *args],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReaderEvidenceIntegrationError("unable to read immutable repository evidence") from exc
    return completed.stdout


def resolve_checkout_context(repository_root: Path) -> dict[str, str]:
    try:
        commit_sha = _git(repository_root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip().lower()
        tree_sha = _git(repository_root, "rev-parse", "HEAD^{tree}").decode("ascii").strip().lower()
    except UnicodeDecodeError as exc:
        raise ReaderEvidenceIntegrationError("repository identity is not ASCII") from exc
    if not COMMIT_RE.fullmatch(commit_sha) or not COMMIT_RE.fullmatch(tree_sha):
        raise ReaderEvidenceIntegrationError("repository identity is invalid")
    return {"commit_sha": commit_sha, "tree_sha": tree_sha}


def _load_script_module(repository_root: Path, name: str) -> ModuleType:
    scripts_dir = str(Path(repository_root) / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return importlib.import_module(name)


def _snapshot_payload(repository_root: Path, commit_sha: str, identity: dict[str, Any]) -> dict[str, Any]:
    path = identity.get("path")
    expected_sha = identity.get("sha256")
    if not isinstance(path, str) or not path or not isinstance(expected_sha, str):
        raise ReaderEvidenceIntegrationError("selected observation identity is incomplete")
    raw = _git(repository_root, "cat-file", "blob", f"{commit_sha}:{path}")
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ReaderEvidenceIntegrationError("selected observation bytes do not match validated identity")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReaderEvidenceIntegrationError("selected observation payload is invalid") from exc
    if not isinstance(payload, dict):
        raise ReaderEvidenceIntegrationError("selected observation payload must be an object")
    run = payload.get("run")
    if not isinstance(run, dict):
        raise ReaderEvidenceIntegrationError("selected observation run metadata is unavailable")
    if run.get("generated_at_utc") != identity.get("generated_at_utc"):
        raise ReaderEvidenceIntegrationError("selected observation generation time changed")
    if run.get("observation_hour_utc") != identity.get("observation_hour_utc"):
        raise ReaderEvidenceIntegrationError("selected observation hour changed")
    return payload


def _asset_projection(payload: dict[str, Any]) -> list[dict[str, Any]]:
    market = payload.get("market")
    assets = market.get("assets") if isinstance(market, dict) else None
    if not isinstance(assets, list):
        raise ReaderEvidenceIntegrationError("validated observation has no market asset list")
    by_symbol = {
        asset.get("symbol"): asset
        for asset in assets
        if isinstance(asset, dict) and isinstance(asset.get("symbol"), str)
    }
    projected: list[dict[str, Any]] = []
    for symbol in ("BTC", "ETH", "SOL"):
        asset = by_symbol.get(symbol)
        if not isinstance(asset, dict) or not isinstance(asset.get("price_usd"), (int, float)):
            raise ReaderEvidenceIntegrationError(f"validated observation lacks {symbol} price evidence")
        projected.append(
            {
                "symbol": symbol,
                "price_usd": asset["price_usd"],
            }
        )
    return projected


def _source_status(payload: dict[str, Any]) -> dict[str, str]:
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        return {}
    statuses: dict[str, str] = {}
    for name in sorted(sources):
        record = sources[name]
        if isinstance(record, dict) and isinstance(record.get("status"), str):
            statuses[name] = record["status"]
    return statuses


def resolve_current_observation(repository_root: Path, commit_sha: str) -> dict[str, Any] | None:
    resolver = _load_script_module(repository_root, "resolve_crypto_observation_hour_adjacency")
    try:
        population = resolver.load_observation_hour_population(repository_root, commit_sha)
    except resolver.ObservationHourPopulationError:
        return None
    if not population:
        return None

    newest_slot = max(population)
    result = resolver.resolve_observation_hour_adjacency(repository_root, commit_sha, newest_slot)
    current = result.get("current") if isinstance(result, dict) else None
    if not isinstance(current, dict):
        return None
    if current.get("observation_hour_utc") != newest_slot:
        return None
    if current.get("quality_status") not in {"valid-ok", "valid-degraded"}:
        return None

    payload = _snapshot_payload(repository_root, commit_sha, current)
    quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
    run = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    return {
        "identity": current,
        "resolution_status": result.get("resolution_status"),
        "assets": _asset_projection(payload),
        "quality_status": current.get("quality_status"),
        "non_blocking_warnings": list(current.get("non_blocking_warnings") or []),
        "required_sources": list(quality.get("required_sources") or []),
        "disabled_sources": list(quality.get("disabled_sources") or []),
        "source_status": _source_status(payload),
        "generated_at_local": run.get("generated_at_local"),
        "timezone_abbreviation": run.get("timezone_abbreviation"),
    }


def _report_generation(report: Any) -> str:
    metadata = getattr(report, "metadata", {})
    if isinstance(metadata, dict) and metadata.get("schema_version") == "deterministic-crypto-report/v1":
        return "Deterministic archived report"
    return "AI-generated historical report"


def _report_summary(report: Any | None) -> dict[str, Any] | None:
    if report is None:
        return None
    metadata = getattr(report, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    source_items = getattr(report, "source_items", [])
    return {
        "title": str(getattr(report, "title", "Archived report")),
        "headline": str(getattr(report, "headline", "")),
        "timestamp": str(getattr(report, "timestamp", "")),
        "url": str(getattr(report, "url", "")),
        "source_snapshot": metadata.get("source_snapshot") if isinstance(metadata.get("source_snapshot"), str) else None,
        "generation": _report_generation(report),
        "citation_count": len(source_items) if isinstance(source_items, list) else 0,
    }


def build_reader_evidence_context(base: Any) -> dict[str, Any]:
    root = Path(base.ROOT)
    repository_context = resolve_checkout_context(root)
    reports = base.collect_reports()
    latest_report = reports[0] if reports else None
    current_observation = resolve_current_observation(root, repository_context["commit_sha"])
    latest_summary = _report_summary(latest_report)

    relation = "unavailable"
    if latest_summary is not None and current_observation is not None:
        relation = (
            "exact-source-snapshot-match"
            if latest_summary.get("source_snapshot") == current_observation["identity"].get("path")
            else "different-evidence-objects"
        )

    return {
        "repository_context": repository_context,
        "canonical_report_chronology": [getattr(report, "report_time_utc", getattr(report, "sort_key", "")) for report in reports],
        "latest_report": latest_summary,
        "current_observation": current_observation,
        "report_observation_relation": relation,
    }


def _format_price(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "Unavailable"
    if value >= 1000:
        return f"US${value:,.2f}"
    return f"US${value:,.4f}".rstrip("0").rstrip(".")


def _observation_time(observation: dict[str, Any]) -> str:
    local = observation.get("generated_at_local")
    abbreviation = observation.get("timezone_abbreviation")
    if isinstance(local, str) and local:
        try:
            text = local.replace("Z", "+00:00")
            from datetime import datetime

            parsed = datetime.fromisoformat(text)
            suffix = f" {abbreviation}" if isinstance(abbreviation, str) and abbreviation else ""
            return f"{parsed:%Y-%m-%d %H:%M:%S}{suffix}"
        except ValueError:
            pass
    generated = observation.get("identity", {}).get("generated_at_utc")
    return str(generated or "Unavailable")


def _safety_panel() -> str:
    return """
      <section class="reader-safety" aria-label="CryptoPulse demo and use limitations">
        <div class="eyebrow">Demo evidence — not for trading</div>
        <p><strong>CryptoPulse is a prototype demonstration.</strong> It combines deterministic repository-backed evidence with preserved historical report content, including AI-generated reports that may be inaccurate, incomplete, stale, misleading or hallucinated. Deterministic values shown below are static evidence from the checked-out repository, not live market data.</p>
        <p>Nothing here is financial advice, investment research, a recommendation or a trading signal. Do not use this site as a basis for trading, investing or risk decisions.</p>
      </section>
    """


def _market_cards(observation: dict[str, Any]) -> str:
    cards = []
    for asset in observation["assets"]:
        cards.append(
            '<article class="reader-market-card">'
            f'<span>{html.escape(asset["symbol"])}</span>'
            f'<strong>{html.escape(_format_price(asset["price_usd"]))}</strong>'
            '<small>Exact validated point observation</small>'
            "</article>"
        )
    return "".join(cards)


def _health(observation: dict[str, Any]) -> str:
    quality = html.escape(str(observation.get("quality_status") or "unavailable"))
    statuses = observation.get("source_status") or {}
    required = observation.get("required_sources") or []
    required_text = ", ".join(
        f"{name}: {statuses.get(name, 'unavailable')}" for name in required
    ) or "No required-source summary available"
    disabled = ", ".join(observation.get("disabled_sources") or []) or "None"
    predecessor = observation.get("resolution_status")
    comparison_note = (
        "Previous-hour comparison is unavailable; no change-through-time claim is inferred."
        if predecessor and predecessor != "adjacency-resolved"
        else "Exact predecessor evidence is available under the frozen Phase 13 boundary."
    )
    return (
        '<section class="reader-evidence-health" aria-label="Evidence health">'
        '<div class="eyebrow">Evidence health</div>'
        f"<p><strong>{quality}</strong> — required sources: {html.escape(required_text)}.</p>"
        f"<p>Disabled sources: {html.escape(disabled)}. {html.escape(comparison_note)}</p>"
        "</section>"
    )


def _report_block(report: dict[str, Any] | None, relation: str) -> str:
    if report is None:
        return (
            '<section class="reader-report-summary" aria-label="Most recent archived report">'
            '<div class="eyebrow">Most recent archived report</div><p>No archived report is available.</p></section>'
        )
    citations = (
        f"{report['citation_count']} embedded report source item(s)"
        if report["citation_count"]
        else "No embedded report citation list"
    )
    provenance = report.get("source_snapshot") or "No governed source_snapshot declared by this report format"
    relation_note = {
        "exact-source-snapshot-match": "This archived report is attached to the selected observation by exact source_snapshot path equality.",
        "different-evidence-objects": "This archived report and the selected observation are different evidence objects; no values, citations or status are copied between them.",
        "unavailable": "No report/observation association is asserted.",
    }[relation]
    return f"""
      <section class="reader-report-summary" aria-label="Most recent archived report">
        <div class="eyebrow">Most recent archived report</div>
        <h2><a href="{html.escape(report['url'], quote=True)}">{html.escape(report['title'])}</a></h2>
        <p class="muted">{html.escape(report['timestamp'])} · {html.escape(report['generation'])}</p>
        <p>{html.escape(report['headline'])}</p>
        <dl class="reader-report-evidence"><div><dt>Report citations</dt><dd>{html.escape(citations)}</dd></div><div><dt>Underlying data provenance</dt><dd><code>{html.escape(provenance)}</code></dd></div></dl>
        <p>{html.escape(relation_note)}</p>
      </section>
    """


def render_reader_panel(context: dict[str, Any], *, surface: str) -> str:
    observation = context.get("current_observation")
    report = context.get("latest_report")
    relation = context.get("report_observation_relation", "unavailable")
    repo = context["repository_context"]

    if isinstance(observation, dict):
        observation_html = f"""
      <section class="reader-observation" aria-label="Most recent available repository observation">
        <div class="eyebrow">Most recent available repository observation</div>
        <h2>Validated point-in-time market evidence</h2>
        <p class="reader-evidence-time">Observed {html.escape(_observation_time(observation))}</p>
        <div class="reader-market-grid">{_market_cards(observation)}</div>
        {_health(observation)}
      </section>
        """
    else:
        observation_html = """
      <section class="reader-observation reader-observation-unavailable" aria-label="Repository observation unavailable">
        <div class="eyebrow">Most recent available repository observation</div>
        <h2>Deterministic observation unavailable</h2>
        <p>The newest participating repository observation could not be used safely. No older observation is substituted and no deterministic market cards are shown.</p>
      </section>
        """

    surface_note = (
        '<p class="reader-surface-note">Home summarises the best available repository evidence while keeping the archived report as a separate historical object.</p>'
        if surface == "home"
        else '<p class="reader-surface-note">This compatibility URL presents the most recent available repository evidence; the preserved archived report remains separate below.</p>'
    )
    return f"""
    <section class="reader-evidence" data-reader-surface="{html.escape(surface)}">
      {_safety_panel()}
      {surface_note}
      {observation_html}
      <section class="reader-taxonomy" aria-label="Evidence types">
        <div class="eyebrow">Evidence types</div>
        <p><strong>Deterministic repository-backed evidence</strong> is projected from validated committed source data. <strong>Historical report content</strong> keeps the generation semantics and citation limits of its own archived report. Static HTML generation performs no new model inference.</p>
      </section>
      {_report_block(report, relation)}
      <div class="reader-evidence-actions"><a class="button" href="latest.html">Most recent</a><a class="text-link" href="archive/index.html">Archive →</a></div>
      <details class="reader-evidence-inspect"><summary>Inspect the evidence</summary><dl><div><dt>Repository commit</dt><dd><code>{html.escape(repo['commit_sha'])}</code></dd></div><div><dt>Repository tree</dt><dd><code>{html.escape(repo['tree_sha'])}</code></dd></div>{_observation_inspect(observation)}</dl></details>
    </section>
    """


def _observation_inspect(observation: dict[str, Any] | None) -> str:
    if not isinstance(observation, dict):
        return '<div><dt>Observation</dt><dd>Unavailable</dd></div>'
    identity = observation["identity"]
    return (
        f'<div><dt>Observation hour</dt><dd><code>{html.escape(str(identity.get("observation_hour_utc")))}</code></dd></div>'
        f'<div><dt>Source snapshot</dt><dd><code>{html.escape(str(identity.get("path")))}</code></dd></div>'
        f'<div><dt>Snapshot SHA-256</dt><dd><code>{html.escape(str(identity.get("sha256")))}</code></dd></div>'
    )


def _remove_optional_once(source: str, pattern: re.Pattern[str], label: str) -> str:
    source, count = pattern.subn("\n", source, count=2)
    if count > 1:
        raise ReaderEvidenceIntegrationError(f"unexpected duplicate {label} blocks")
    return source


def _replace_required_once(source: str, pattern: re.Pattern[str], replacement: str, label: str) -> str:
    source, count = pattern.subn(replacement, source, count=2)
    if count != 1:
        raise ReaderEvidenceIntegrationError(f"expected exactly one {label} anchor")
    return source


def _stylesheet(source: str) -> str:
    if STYLE_NAME in source:
        return source
    if source.count("</head>") != 1:
        raise ReaderEvidenceIntegrationError("expected exactly one head close tag")
    return source.replace("</head>", f'  <link rel="stylesheet" href="assets/{STYLE_NAME}">\n</head>', 1)


def _reader_demo_framing(source: str) -> str:
    old_body = (
        "Reports on this site are AI-created examples used to show what automated market-report "
        "publishing could look like. They may be inaccurate, incomplete, outdated, or misleading. "
        "Do not use them for trading or investment decisions."
    )
    new_body = (
        "CryptoPulse is a prototype demonstration combining deterministic repository-backed evidence "
        "with preserved historical report content, including AI-generated reports that may be "
        "inaccurate, incomplete, outdated, misleading, or hallucinated. Do not use this site for "
        "trading or investment decisions."
    )
    if source.count(old_body) != 1:
        raise ReaderEvidenceIntegrationError("expected exactly one demo notice body")
    source = source.replace(old_body, new_body, 1)
    source = source.replace("<span>AI-generated</span>", "<span>Repository evidence</span>", 1)
    return source


def transform_home(source: str, context: dict[str, Any]) -> str:
    source = _reader_demo_framing(source)
    source = _remove_optional_once(source, LATEST_MARKET_READ_RE, "legacy latest-market-read")
    source = _remove_optional_once(source, LATEST_FEATURE_RE, "legacy latest-feature")
    source = source.replace(">Latest Report</a>", ">Most recent</a>")
    source = source.replace("Latest report</div>", "Most recent archived report</div>")
    source = source.replace("Latest headline</div>", "Archived report headline</div>")

    actions = """
        <div class="hero-actions" aria-label="Primary actions">
          <a class="button hero-primary-action" href="latest.html">Most recent</a>
          <a class="button secondary-button" href="archive/index.html">Archive</a>
          <a class="button ghost-button" href="search.html">Search archive</a>
        </div>
    """
    if HERO_ACTIONS_RE.search(source):
        source = _replace_required_once(source, HERO_ACTIONS_RE, actions, "homepage hero actions")

    panel = render_reader_panel(context, surface="home")
    source = _replace_required_once(source, HOME_HERO_RE, lambda_match_wrapper(panel), "homepage hero")
    return _stylesheet(source)


def lambda_match_wrapper(panel: str):
    return lambda match: match.group(1) + "\n" + panel


def transform_latest(source: str, context: dict[str, Any]) -> str:
    source = _reader_demo_framing(source)
    source = source.replace(">Latest Report</a>", ">Most recent</a>")
    source = re.sub(
        r"<title>.*?</title>",
        "<title>Most recent available market evidence | CryptoPulse Demo</title>",
        source,
        count=1,
        flags=re.DOTALL,
    )

    def replace_hero(match: re.Match[str]) -> str:
        hero = match.group(1)
        hero, h_count = re.subn(r"<h1>.*?</h1>", "<h1>Most recent available market evidence</h1>", hero, count=1, flags=re.DOTALL)
        hero, p_count = re.subn(
            r"<p>.*?</p>",
            "<p>Repository-recency evidence and preserved historical report content, kept as distinct authorities.</p>",
            hero,
            count=1,
            flags=re.DOTALL,
        )
        if h_count != 1 or p_count != 1:
            raise ReaderEvidenceIntegrationError("latest report hero structure is unavailable")
        return hero + "\n" + render_reader_panel(context, surface="latest")

    source, count = LATEST_HERO_RE.subn(replace_hero, source, count=2)
    if count != 1:
        raise ReaderEvidenceIntegrationError("expected exactly one latest report hero")
    return _stylesheet(source)


def copy_style(base: Any) -> None:
    source = Path(base.SITE_SRC) / "assets" / STYLE_NAME
    destination = Path(base.OUT) / "assets" / STYLE_NAME
    if not source.exists():
        raise ReaderEvidenceIntegrationError(f"missing Phase 16 stylesheet: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)


def apply(base: Any) -> None:
    """Apply one shared reader context to Home and latest.html or fail the build."""
    copy_style(base)
    context = build_reader_evidence_context(base)
    targets = (
        (Path(base.OUT) / "index.html", transform_home),
        (Path(base.OUT) / "latest.html", transform_latest),
    )
    for path, transform in targets:
        if not path.exists():
            raise ReaderEvidenceIntegrationError(f"required reader surface is unavailable: {path.name}")
        source = path.read_text(encoding="utf-8")
        path.write_text(transform(source, context), encoding="utf-8")


__all__ = [
    "ReaderEvidenceIntegrationError",
    "apply",
    "build_reader_evidence_context",
    "render_reader_panel",
    "resolve_checkout_context",
    "resolve_current_observation",
    "transform_home",
    "transform_latest",
]
