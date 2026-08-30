"""Capture and assert evidence from the deployed CryptoPulse GitHub Pages site."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

BASE_URL = "https://8ft0-ai.github.io/crypto-pulse/"
CORE_PATHS = {
    "homepage": "",
    "latest-report": "latest.html",
    "archive": "archive/",
    "search": "search.html",
}
BAD_METRIC = "ETH, L2s, DeFi majors"
BAD_STATUS = "Data not specified"
DISCLAIMER_MARKERS = (
    "not financial advice",
    "deterministic demonstration content",
)
TIME_WITH_ZONE = re.compile(r"\b\d{2}:\d{2}\s+(?:AEST|AEDT|UTC|GMT)\b")


def duplicate_metric_labels(card_text: str) -> list[str]:
    """Return BTC/ETH metric labels repeated within one rendered card."""
    labels = re.findall(r"\b(?:BTC|ETH)\s+(?:1h|24h)\b", card_text, re.IGNORECASE)
    normalised = [label.upper().replace(" ", "_") for label in labels]
    return sorted({label for label in normalised if normalised.count(label) > 1})


def primary_headline_is_boilerplate(text: str) -> bool:
    """Identify disclaimer copy incorrectly promoted into the latest-headline card."""
    lowered = " ".join(text.lower().split())
    return any(marker in lowered for marker in DISCLAIMER_MARKERS)


def accessible_name_missing(
    role_text: str,
    aria_label: str | None,
    title: str | None,
    *,
    visible: bool = True,
) -> bool:
    """Return whether a visible interactive control lacks any accessible naming signal."""
    if not visible:
        return False
    return not any((role_text or "").strip() for role_text in (role_text, aria_label or "", title or ""))


def normalise_axe_results(raw: dict[str, Any]) -> dict[str, Any]:
    """Preserve actionable Axe rule and node evidence in a stable JSON shape."""
    violations: list[dict[str, Any]] = []
    for violation in raw.get("violations", []):
        nodes: list[dict[str, Any]] = []
        for node in violation.get("nodes", []):
            nodes.append(
                {
                    "target": node.get("target", []),
                    "html": node.get("html", ""),
                    "failureSummary": node.get("failureSummary", ""),
                    "foreground": node.get("foreground"),
                    "background": node.get("background"),
                    "fontSize": node.get("fontSize"),
                    "fontWeight": node.get("fontWeight"),
                }
            )
        violations.append(
            {
                "id": violation.get("id", ""),
                "impact": violation.get("impact"),
                "description": violation.get("description", ""),
                "help": violation.get("help", ""),
                "helpUrl": violation.get("helpUrl", ""),
                "nodes": nodes,
            }
        )
    return {"violations": violations}


def _goto_with_retry(page: Any, url: str, attempts: int = 6) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = page.goto(url, wait_until="networkidle", timeout=45_000)
            if response and response.status == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status if response else 'no response'} for {url}")
        except Exception as exc:  # Playwright errors are reported in the final result.
            last_error = exc
        time.sleep(min(5 * (attempt + 1), 20))
    raise RuntimeError(f"Unable to load {url}: {last_error}")


def _capture_page(page: Any, name: str, url: str, output: Path, axe_source: str) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    response = _goto_with_retry(page, url)
    html = page.content()
    text = page.locator("body").inner_text()
    (output / f"{name}.html").write_text(html, encoding="utf-8")
    (output / f"{name}.txt").write_text(text, encoding="utf-8")
    page.screenshot(path=str(output / f"{name}.png"), full_page=True)

    title = page.title()
    headings = page.locator("h1").all_inner_texts()
    skip_links = page.locator('a[href^="#"]').all_inner_texts()
    controls = page.locator("a, button").evaluate_all(
        """els => els.map(el => ({
          text: (el.innerText || '').trim(),
          aria: el.getAttribute('aria-label'),
          title: el.getAttribute('title'),
          visible: typeof el.checkVisibility === 'function'
            ? el.checkVisibility()
            : !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
        }))"""
    )
    unnamed = [
        control
        for control in controls
        if accessible_name_missing(
            control["text"],
            control["aria"],
            control["title"],
            visible=control["visible"],
        )
    ]

    page.add_script_tag(content=axe_source)
    raw_axe = page.evaluate(
        """async () => {
          const result = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}});
          return {
            violations: result.violations.map(v => ({
              id: v.id,
              impact: v.impact,
              description: v.description,
              help: v.help,
              helpUrl: v.helpUrl,
              nodes: v.nodes.map(node => {
                let element = null;
                try {
                  const selector = Array.isArray(node.target) ? node.target[0] : node.target;
                  element = selector ? document.querySelector(selector) : null;
                } catch (_) {
                  element = null;
                }
                const style = element ? window.getComputedStyle(element) : null;
                return {
                  target: node.target,
                  html: node.html,
                  failureSummary: node.failureSummary,
                  foreground: style ? style.color : null,
                  background: style ? style.backgroundColor : null,
                  fontSize: style ? style.fontSize : null,
                  fontWeight: style ? style.fontWeight : null
                };
              })
            }))
          };
        }"""
    )
    axe = normalise_axe_results(raw_axe)
    serious = [item for item in axe["violations"] if item.get("impact") in {"serious", "critical"}]

    failures: list[str] = []
    if response.status != 200:
        failures.append(f"{name}: expected HTTP 200, got {response.status}")
    if not title.strip():
        failures.append(f"{name}: missing page title")
    if len(headings) != 1 or not headings[0].strip():
        failures.append(f"{name}: expected one meaningful h1, got {headings!r}")
    if not any("skip" in item.lower() for item in skip_links):
        failures.append(f"{name}: missing skip link")
    if unnamed:
        failures.append(f"{name}: {len(unnamed)} links/buttons lack accessible names")
    if serious:
        failures.append(f"{name}: {len(serious)} serious/critical Axe violations")

    details = {
        "url": url,
        "status": response.status,
        "title": title,
        "primary_heading": headings[0] if headings else "",
        "skip_link": any("skip" in item.lower() for item in skip_links),
        "unnamed_controls": len(unnamed),
        "serious_accessibility_violations": len(serious),
    }
    return details, failures, {"page": name, **axe}


def run() -> int:
    """Run live verification, write evidence even on failure, and return an exit code."""
    from playwright.sync_api import sync_playwright

    base_url = os.environ.get("CRYPTOPULSE_BASE_URL", BASE_URL).rstrip("/") + "/"
    output = Path(os.environ.get("EVIDENCE_DIR", "live-site-evidence"))
    output.mkdir(parents=True, exist_ok=True)
    axe_path = Path(os.environ.get("AXE_PATH", "node_modules/axe-core/axe.min.js"))
    if not axe_path.exists():
        raise FileNotFoundError(f"Axe source not found at {axe_path}")
    axe_source = axe_path.read_text(encoding="utf-8")

    result: dict[str, Any] = {
        "deployment_commit": os.environ.get("DEPLOYMENT_COMMIT", "unknown"),
        "base_url": base_url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "pages": {},
        "failures": [],
    }
    accessibility: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        for name, path in CORE_PATHS.items():
            details, failures, axe = _capture_page(page, name, urljoin(base_url, path), output, axe_source)
            result["pages"][name] = details
            result["failures"].extend(failures)
            accessibility.append(axe)

        homepage_text = (output / "homepage.txt").read_text(encoding="utf-8")
        archive_text = (output / "archive.txt").read_text(encoding="utf-8")

        _goto_with_retry(page, urljoin(base_url, ""))
        cards = page.locator(".archive-preview-card").all_inner_texts()
        duplicate_labels = sorted({label for card in cards for label in duplicate_metric_labels(card)})
        recent_cards_have_time = bool(cards[:2]) and all(TIME_WITH_ZONE.search(card) for card in cards[:2])
        headline_card = ""
        label = page.get_by_text("Latest headline", exact=True)
        if label.count():
            headline_card = label.first.locator("xpath=..").inner_text()

        homepage_checks = {
            "contains_not_specified": BAD_STATUS.lower() in homepage_text.lower(),
            "duplicate_metric_groups": duplicate_labels,
            "recent_cards_have_time_and_timezone": recent_cards_have_time,
            "primary_latest_headline_is_boilerplate": primary_headline_is_boilerplate(headline_card),
        }
        result["pages"]["homepage"].update(homepage_checks)
        if homepage_checks["contains_not_specified"]:
            result["failures"].append("homepage: contains 'Data not specified'")
        if duplicate_labels:
            result["failures"].append(f"homepage: duplicate metric labels within cards: {duplicate_labels}")
        if not recent_cards_have_time:
            result["failures"].append("homepage: recent archive cards lack visible time and timezone")
        if homepage_checks["primary_latest_headline_is_boilerplate"]:
            result["failures"].append("homepage: disclaimer boilerplate is used as the primary latest headline")

        invalid_metric = BAD_METRIC.lower() in archive_text.lower()
        result["pages"]["archive"]["contains_invalid_eth_metric"] = invalid_metric
        if invalid_metric:
            result["failures"].append(f"archive: contains invalid legacy metric '{BAD_METRIC}'")

        nav_hrefs = page.locator("nav a").evaluate_all("els => els.map(el => el.href)")
        broken_nav: list[str] = []
        for href in nav_hrefs:
            response = page.request.get(href)
            if response.status >= 400:
                broken_nav.append(f"{href} ({response.status})")
        result["navigation"] = {"checked": len(nav_hrefs), "broken": broken_nav}
        if broken_nav:
            result["failures"].append(f"navigation: broken links: {broken_nav}")
        browser.close()

    (output / "accessibility.json").write_text(json.dumps(accessibility, indent=2), encoding="utf-8")
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(run())
