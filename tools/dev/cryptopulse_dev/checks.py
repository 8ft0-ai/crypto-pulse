from __future__ import annotations

from pathlib import Path

from .process import ProcessRunner

EXPECTED_SITE_ARTIFACTS = (
    "_site/index.html",
    "_site/latest.html",
    "_site/archive/index.html",
    "_site/search.html",
    "_site/search-index.json",
    "_site/manifest.json",
    "_site/feed.xml",
    "_site/assets/cryptopulse.css",
    "_site/assets/cryptopulse-report-ux.css",
    "_site/assets/cryptopulse-report-ux.js",
    "_site/assets/cryptopulse-brief-glance.css",
    "_site/assets/cryptopulse-structured-sources.css",
    "_site/assets/cryptopulse-search-filters.css",
    "_site/assets/cryptopulse-accessibility.css",
)


def tracked_site_paths(root: Path, runner: ProcessRunner) -> tuple[str, ...]:
    result = runner.run(["git", "ls-files", "--", "_site"], cwd=root, capture=True)
    if result.returncode != 0:
        return ("<unable to inspect tracked _site output>",)
    return tuple(line for line in result.stdout.splitlines() if line.strip())


def missing_site_artifacts(root: Path) -> tuple[str, ...]:
    return tuple(path for path in EXPECTED_SITE_ARTIFACTS if not (root / path).is_file())
