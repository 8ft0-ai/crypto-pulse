from site_verification.actions_summary import (
    annotation_data,
    failure_annotations,
    markdown_cell,
    render_summary,
)


def sample_result(failures=None):
    return {
        "deployment_commit": "abc123",
        "base_url": "https://example.test/",
        "checked_at": "2026-07-10T12:03:00+00:00",
        "pages": {
            "homepage": {
                "status": 200,
                "primary_heading": "CryptoPulse",
                "serious_accessibility_violations": 0,
                "recent_cards_have_time_and_timezone": True,
                "contains_not_specified": False,
                "duplicate_metric_groups": [],
                "primary_latest_headline_is_boilerplate": False,
            },
            "latest-report": {
                "status": 200,
                "primary_heading": "Crypto Market Intelligence",
                "serious_accessibility_violations": 0,
            },
            "archive": {
                "status": 200,
                "primary_heading": "Report archive",
                "serious_accessibility_violations": 0,
                "contains_invalid_eth_metric": False,
            },
            "search": {
                "status": 200,
                "primary_heading": "Search reports",
                "serious_accessibility_violations": 0,
            },
        },
        "navigation": {"checked": 4, "broken": []},
        "failures": failures or [],
    }


def test_render_summary_shows_passed_pages_and_regression_checks():
    summary = render_summary(sample_result())

    assert "**Result:** ✅ Passed" in summary
    assert "`abc123`" in summary
    assert "| Homepage | 200 | CryptoPulse | 0 | ✅ |" in summary
    assert "| Latest report | 200 | Crypto Market Intelligence | 0 | ✅ |" in summary
    assert "✅ Recent archive cards show time and timezone" in summary
    assert "✅ Navigation links resolve — 4 checked" in summary
    assert "No verification failures." in summary
    assert "cryptopulse-live-site-evidence" in summary


def test_render_summary_marks_failed_page_and_lists_failure():
    failure = "latest-report: 1 serious/critical Axe violations"
    summary = render_summary(sample_result([failure]))

    assert "**Result:** ❌ Failed" in summary
    assert "| Latest report | 200 | Crypto Market Intelligence | 0 | ❌ |" in summary
    assert f"- ❌ {failure}" in summary


def test_annotation_and_markdown_escaping_are_stable():
    assert markdown_cell("A | B\nC") == "A \\| B C"
    assert annotation_data("bad%value\r\nnext") == "bad%25value%0D%0Anext"
    assert failure_annotations(["archive: broken\nlink"]) == [
        "::error title=CryptoPulse live verification::archive: broken%0Alink"
    ]
