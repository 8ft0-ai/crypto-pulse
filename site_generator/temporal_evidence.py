"""Canonical public-site integration for Phase 15 temporal evidence."""

from __future__ import annotations

import html
import importlib
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

DISCOVERY_RE = re.compile(
    r'<section class="temporal-evidence-discovery"[^>]*>.*?</section>\n?',
    re.DOTALL,
)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class TemporalEvidenceIntegrationError(ValueError):
    """Raised when the site cannot safely assert Phase 15 evidence."""


def _load_script_module(repository_root: Path, name: str) -> ModuleType:
    scripts_dir = str(Path(repository_root) / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return importlib.import_module(name)


def resolve_checkout_commit(repository_root: Path) -> str:
    """Resolve the exact immutable Git commit checked out for this site build."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "--verify", "HEAD^{commit}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TemporalEvidenceIntegrationError("unable to resolve checked-out Git commit") from exc

    commit_sha = result.stdout.strip().lower()
    if not COMMIT_RE.fullmatch(commit_sha):
        raise TemporalEvidenceIntegrationError("checked-out Git commit identity is invalid")
    return commit_sha


def _remove_discovery_link(index_path: Path) -> None:
    if not index_path.exists():
        return
    source = index_path.read_text(encoding="utf-8")
    cleaned = DISCOVERY_RE.sub("", source)
    if cleaned != source:
        index_path.write_text(cleaned, encoding="utf-8")


def _add_discovery_link(index_path: Path) -> None:
    source = index_path.read_text(encoding="utf-8")
    if "temporal-evidence-discovery" in source:
        return
    marker = '<footer class="footer">'
    if marker not in source:
        raise TemporalEvidenceIntegrationError("homepage footer marker is unavailable")
    discovery = (
        '<section class="temporal-evidence-discovery" aria-label="Deterministic temporal evidence">'
        '<div class="eyebrow">Repository evidence</div>'
        '<p><a class="text-link" href="temporal.html">View deterministic temporal evidence →</a></p>'
        '</section>\n'
    )
    index_path.write_text(source.replace(marker, discovery + marker, 1), encoding="utf-8")


def _page(base: Any, commit_sha: str, rendered_evidence: str) -> str:
    escaped_commit = html.escape(commit_sha, quote=True)
    return f"""<!doctype html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Deterministic temporal evidence | {html.escape(base.SITE_NAME)}</title>
  <link rel="stylesheet" href="assets/cryptopulse.css">
</head>
<body>
  <main class="page">
    <article class="brief">
      {base.demo_banner()}
      {base.nav()}
      <header class="hero temporal-evidence-hero">
        <div class="brandline"><span class="mark">CP</span> {html.escape(base.SITE_NAME)}</div>
        <h1>Deterministic temporal evidence</h1>
        <p>Repository-bound historical BTC price evidence from one immutable checked-out commit.</p>
        {base.badges()}
      </header>
      <section class="temporal-evidence-disclaimer" aria-label="Temporal evidence limitations">
        <div class="eyebrow">Historical demo evidence</div>
        <h2>Evidence, not a market call</h2>
        <p>This page is AI-demo infrastructure output built from historical repository evidence. It is not a forecast, investment research, recommendation, trading signal, market call, or financial advice.</p>
        <p>No interpolation, aggregation, smoothing, backfill, inferred trend, generated narrative, or live-data fallback is introduced.</p>
      </section>
      <section class="temporal-evidence-context" aria-label="Evidence authority">
        <div><span>Repository commit</span><strong><code>{escaped_commit}</code></strong></div>
        <div><span>Contract</span><strong><code>phase15-public-temporal-evidence/v1</code></strong></div>
        <div><span>Series</span><strong><code>metric / BTC.price_usd / 24 UTC-hour slots</code></strong></div>
      </section>
      <section class="content temporal-evidence-content">
        {rendered_evidence}
      </section>
      {base.footer()}
    </article>
  </main>
</body>
</html>
"""


def apply(base: Any) -> bool:
    """Create temporal.html and its homepage link only from one validated commit."""
    root = Path(base.ROOT)
    out_dir = Path(base.OUT)
    index_path = out_dir / "index.html"
    temporal_path = out_dir / "temporal.html"

    temporal_path.unlink(missing_ok=True)
    _remove_discovery_link(index_path)
    if not index_path.exists():
        return False

    try:
        commit_sha = resolve_checkout_commit(root)
        phase15 = _load_script_module(root, "phase15_public_temporal_evidence")
        phase13 = _load_script_module(root, "crypto_observation_hour_series")
        renderer = _load_script_module(root, "render_crypto_observation_hour_series")

        record = phase15.build_public_temporal_evidence(root, commit_sha)
        if record is None:
            return False
        repository_context = record.get("repository_context")
        if not isinstance(repository_context, dict) or repository_context.get("commit_sha") != commit_sha:
            raise TemporalEvidenceIntegrationError("Phase 15 evidence commit does not match the checked-out commit")

        phase13.validate_observation_hour_series(root, record)
        rendered = renderer.render_observation_hour_series(root, record)
        page = _page(base, commit_sha, rendered)

        temporal_path.write_text(page, encoding="utf-8")
        _add_discovery_link(index_path)
        return True
    except (
        TemporalEvidenceIntegrationError,
        ValueError,
        OSError,
        subprocess.SubprocessError,
    ):
        temporal_path.unlink(missing_ok=True)
        _remove_discovery_link(index_path)
        return False
