from site_verification.live_pages import (
    accessible_name_missing,
    duplicate_metric_labels,
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
