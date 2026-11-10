from site_generator import report_provenance


def test_transform_moves_quality_up_and_removes_duplicate_warning():
    html = '''<html><head></head><body>
      <section class="report-warning compact-warning"><p>This report is AI-generated demo content.</p></section>
      <section class="brief-glance-panel"><div class="brief-glance-grid">
        <article class="brief-glance-card"><span>Market regime</span><strong>Not specified in archived report.</strong></article>
        <article class="brief-glance-card"><span>Data quality</span><strong>Snapshot valid</strong></article>
      </div></section>
      <section class="report-data-quality-panel"><h2>Verification and data limitations</h2></section>
      <section class="structured-source-panel"><h2>Structured sources</h2></section>
    </body></html>'''
    transformed = report_provenance.transform_report_html(html)

    assert 'report-warning compact-warning' not in transformed
    assert transformed.index('report-provenance-lead') < transformed.index('brief-glance-panel')
    assert transformed.index('report-data-quality-panel') < transformed.index('brief-glance-panel')
    assert 'Not specified in archived report.' not in transformed
    assert 'Snapshot valid' in transformed
    assert 'report-format-note' in transformed
    assert 'structured-source-panel' in transformed


def test_transform_suppresses_disclaimer_from_extracted_summary():
    html = '''<section class="brief-glance-panel"><div class="brief-glance-grid">
      <article class="brief-glance-card"><span>Analyst read</span><strong>This is not financial advice.</strong></article>
      <article class="brief-glance-card"><span>BTC / ETH</span><strong>BTC 24h +1.2%</strong></article>
    </div></section><section class="headline"></section>'''
    transformed = report_provenance.transform_report_html(html)

    assert 'This is not financial advice.' not in transformed
    assert 'BTC 24h +1.2%' in transformed
    assert 'No LLM calls during site build' in transformed
    assert 'No hidden enrichment' in transformed
    assert 'No committed <code>_site/</code>' in transformed
