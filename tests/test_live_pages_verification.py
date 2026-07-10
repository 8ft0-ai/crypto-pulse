from site_verification.live_pages import (
    accessible_name_missing,
    duplicate_metric_labels,
    normalise_axe_results,
    primary_headline_is_boilerplate,
)


def test_duplicate_metric_labels_detects_repeated_card_slots():
    text = "BTC 24h\n-1.0%\nETH 24h\n-2.0%\nBTC 24h\n-1.0%"
    assert duplicate_metric_labels(text) == ["BTC_24H"]


def test_duplicate_metric_labels_allows_one_stable_group():
    text = "BTC 24h\n-1.0%\nETH 24h\n-2.0%"
    assert duplicate_metric_labels(text) == []


def test_primary_headline_rejects_product_boundary_boilerplate():
    assert primary_headline_is_boilerplate(
        "This is deterministic demonstration content and not financial advice."
    )
    assert not primary_headline_is_boilerplate(
        "Source-provided market fields are listed without interpretation."
    )


def test_accessible_name_accepts_text_aria_or_title():
    assert accessible_name_missing("", None, None)
    assert not accessible_name_missing("Archive", None, None)
    assert not accessible_name_missing("", "Open archive", None)
    assert not accessible_name_missing("", None, "Open archive")


def test_normalise_axe_results_preserves_actionable_node_evidence():
    raw = {
        "violations": [
            {
                "id": "color-contrast",
                "impact": "serious",
                "description": "Ensure sufficient contrast",
                "help": "Elements must meet contrast thresholds",
                "helpUrl": "https://dequeuniversity.com/rules/axe/color-contrast",
                "nodes": [
                    {
                        "target": [".data-quality-unavailable span"],
                        "html": '<span>Live data</span>',
                        "failureSummary": "Expected contrast ratio of at least 4.5:1",
                        "foreground": "rgb(100, 116, 139)",
                        "background": "rgba(0, 0, 0, 0)",
                        "fontSize": "10px",
                        "fontWeight": "850",
                    }
                ],
            }
        ]
    }

    result = normalise_axe_results(raw)
    violation = result["violations"][0]
    node = violation["nodes"][0]

    assert violation["id"] == "color-contrast"
    assert violation["helpUrl"].endswith("color-contrast")
    assert node["target"] == [".data-quality-unavailable span"]
    assert node["html"] == '<span>Live data</span>'
    assert "4.5:1" in node["failureSummary"]
    assert node["foreground"] == "rgb(100, 116, 139)"
    assert node["background"] == "rgba(0, 0, 0, 0)"
    assert node["fontSize"] == "10px"
    assert node["fontWeight"] == "850"
