from site_generator import homepage_hierarchy


def sample_homepage() -> str:
    return '''<html><head></head><body>
<header class="hero landing-hero product-hero"><div class="hero-actions"><a class="button hero-primary-action" href="archive/latest.html">Open latest report</a></div></header>
<section class="content landing-content">
<section class="stats-grid" aria-label="Archive summary"></section>
<div class="explainer-grid"><section><h2>What this demonstrates</h2></section></div>
<section class="workflow-section"><h2>How this demo works</h2></section>
<section class="latest-market-read" aria-label="Latest market read"><a class="button" href="archive/latest.html">Open source report</a></section>
<section class="latest-feature"><p><a class="button" href="archive/latest.html">Open latest demo report</a></p></section>
</section></body></html>'''


def test_reorders_explanation_before_report_scanning() -> None:
    html = homepage_hierarchy.reorder_sections(sample_homepage())
    assert html.index("homepage-proof") < html.index("explainer-grid")
    assert html.index("explainer-grid") < html.index("workflow-section")
    assert html.index("workflow-section") < html.index("latest-market-read")
    assert html.index("latest-market-read") < html.index("stats-grid")


def test_prioritises_latest_report_actions() -> None:
    html = homepage_hierarchy.prioritise_ctas(sample_homepage())
    assert "Read latest report" in html
    assert "Read full latest report" in html
    assert "View report details →" in html
    assert "Open latest demo report" not in html


def test_adds_mobile_readable_stylesheet_once() -> None:
    html = homepage_hierarchy.add_style(sample_homepage())
    assert html.count(homepage_hierarchy.STYLE_NAME) == 1
    assert homepage_hierarchy.add_style(html).count(homepage_hierarchy.STYLE_NAME) == 1
