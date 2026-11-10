"""Render CryptoPulse live verification results for GitHub Actions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PAGE_ORDER = ("homepage", "latest-report", "archive", "search")
PAGE_LABELS = {
    "homepage": "Homepage",
    "latest-report": "Latest report",
    "archive": "Archive",
    "search": "Search",
}


def markdown_cell(value: Any) -> str:
    """Escape a value for a compact Markdown table cell."""
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def annotation_data(message: str) -> str:
    """Escape GitHub workflow-command data."""
    return str(message).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def failure_annotations(failures: list[str]) -> list[str]:
    """Return one GitHub error workflow command per verification failure."""
    return [f"::error title=CryptoPulse live verification::{annotation_data(failure)}" for failure in failures]


def _page_passed(name: str, result: dict[str, Any]) -> bool:
    prefix = f"{name}:"
    return not any(str(failure).startswith(prefix) for failure in result.get("failures", []))


def _check_line(label: str, passed: bool, detail: str = "") -> str:
    suffix = f" — {detail}" if detail else ""
    return f"- {'✅' if passed else '❌'} {label}{suffix}"


def render_summary(result: dict[str, Any]) -> str:
    """Create a human-readable GitHub Actions job summary."""
    failures = [str(item) for item in result.get("failures", [])]
    passed = not failures
    pages = result.get("pages", {})
    homepage = pages.get("homepage", {})
    archive = pages.get("archive", {})
    navigation = result.get("navigation", {})

    lines = [
        "# CryptoPulse live-site verification",
        "",
        f"**Result:** {'✅ Passed' if passed else '❌ Failed'}  ",
        f"**Deployment:** `{markdown_cell(result.get('deployment_commit', 'unknown'))}`  ",
        f"**Checked:** {markdown_cell(result.get('checked_at', 'unknown'))}  ",
        f"**Site:** {markdown_cell(result.get('base_url', ''))}",
        "",
        "## Pages",
        "",
        "| Page | HTTP | Primary heading | Serious/critical Axe | Result |",
        "|---|---:|---|---:|---|",
    ]

    for name in PAGE_ORDER:
        details = pages.get(name, {})
        page_ok = _page_passed(name, result)
        lines.append(
            "| "
            + " | ".join(
                (
                    PAGE_LABELS[name],
                    markdown_cell(details.get("status", "—")),
                    markdown_cell(details.get("primary_heading", "—")) or "—",
                    markdown_cell(details.get("serious_accessibility_violations", "—")),
                    "✅" if page_ok else "❌",
                )
            )
            + " |"
        )

    duplicate_metrics = homepage.get("duplicate_metric_groups", [])
    broken_links = navigation.get("broken", [])
    lines.extend(
        [
            "",
            "## Regression checks",
            "",
            _check_line("Recent archive cards show time and timezone", bool(homepage.get("recent_cards_have_time_and_timezone"))),
            _check_line("No `Data not specified` placeholder", not bool(homepage.get("contains_not_specified"))),
            _check_line("No duplicate BTC/ETH metric groups", not bool(duplicate_metrics), ", ".join(duplicate_metrics)),
            _check_line("Latest headline is not disclaimer boilerplate", not bool(homepage.get("primary_latest_headline_is_boilerplate"))),
            _check_line("No invalid legacy ETH metric", not bool(archive.get("contains_invalid_eth_metric"))),
            _check_line(
                "Navigation links resolve",
                not bool(broken_links),
                f"{navigation.get('checked', 0)} checked" + (f"; broken: {', '.join(broken_links)}" if broken_links else ""),
            ),
        ]
    )

    lines.extend(["", "## Failures", ""])
    if failures:
        lines.extend(f"- ❌ {failure}" for failure in failures)
    else:
        lines.append("No verification failures.")

    lines.extend(
        [
            "",
            "## Detailed evidence",
            "",
            "The `cryptopulse-live-site-evidence` artifact contains screenshots, rendered HTML, visible text, `result.json`, `accessibility.json`, and this summary.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Write summary.md, append it to the job summary, and emit annotations."""
    evidence_dir = Path(os.environ.get("EVIDENCE_DIR", "live-site-evidence"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    result_path = evidence_dir / "result.json"

    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        result = {
            "deployment_commit": os.environ.get("DEPLOYMENT_COMMIT", "unknown"),
            "base_url": os.environ.get("CRYPTOPULSE_BASE_URL", ""),
            "checked_at": "unknown",
            "pages": {},
            "navigation": {"checked": 0, "broken": []},
            "failures": ["verification did not produce result.json"],
        }

    summary = render_summary(result)
    summary_path = evidence_dir / "summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        with Path(github_summary).open("a", encoding="utf-8") as handle:
            handle.write(summary)
            handle.write("\n")

    for annotation in failure_annotations([str(item) for item in result.get("failures", [])]):
        print(annotation)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
