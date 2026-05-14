(() => {
  const form = document.getElementById('search-form');
  const input = document.getElementById('search-query');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const suggestions = document.querySelectorAll('[data-search-suggestion]');
  const assetFilter = document.getElementById('search-asset');
  const dataQualityFilter = document.getElementById('search-data-quality');
  const trendConfidenceFilter = document.getElementById('search-trend-confidence');
  const dateFromFilter = document.getElementById('search-date-from');
  const dateToFilter = document.getElementById('search-date-to');
  const clearFilters = document.getElementById('search-clear-filters');

  let index = [];
  let loadFailed = false;

  const normalise = (value) => String(value || '').toLowerCase();
  const asArray = (value) => Array.isArray(value) ? value : [];

  const searchableText = (item) => [
    item.title,
    item.timestamp,
    item.headline,
    item.path,
    item.year,
    item.month,
    item.day,
    item.report_date,
    item.trend_confidence,
    item.data_quality,
    item.data_quality_status,
    item.market_regime,
    ...asArray(item.assets),
    ...asArray(item.sources),
    ...asArray(item.structured_source_names),
  ].map(normalise).join(' ');

  const highlight = (text, query) => {
    const safeText = String(text || '');
    if (!query) return safeText;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return safeText.replace(new RegExp(`(${escaped})`, 'ig'), '<mark>$1</mark>');
  };

  const filters = () => ({
    q: input?.value.trim() || '',
    asset: assetFilter?.value || '',
    dataQuality: dataQualityFilter?.value || '',
    trendConfidence: trendConfidenceFilter?.value || '',
    dateFrom: dateFromFilter?.value || '',
    dateTo: dateToFilter?.value || '',
  });

  const hasActiveFilters = (state) => Boolean(
    state.q || state.asset || state.dataQuality || state.trendConfidence || state.dateFrom || state.dateTo
  );

  const filterItem = (item, state) => {
    const terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length && !terms.every((term) => searchableText(item).includes(term))) return false;

    if (state.asset && !asArray(item.assets).map((asset) => String(asset).toUpperCase()).includes(state.asset)) return false;
    if (state.dataQuality && (item.data_quality_status || 'not_specified') !== state.dataQuality) return false;
    if (state.trendConfidence && (item.trend_confidence_bucket || 'not_specified') !== state.trendConfidence) return false;

    const date = item.report_date || '';
    if (state.dateFrom && (!date || date < state.dateFrom)) return false;
    if (state.dateTo && (!date || date > state.dateTo)) return false;

    return true;
  };

  const updateUrl = (state) => {
    const url = new URL(window.location.href);
    const mappings = [
      ['q', state.q],
      ['asset', state.asset],
      ['data_quality', state.dataQuality],
      ['trend_confidence', state.trendConfidence],
      ['date_from', state.dateFrom],
      ['date_to', state.dateTo],
    ];
    mappings.forEach(([key, value]) => {
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    });
    window.history.replaceState({}, '', url);
  };

  const renderEmpty = () => {
    results.innerHTML = '';
    status.textContent = `Loaded ${index.length} archived demo reports. Enter a query or choose filters to begin.`;
  };

  const renderFailure = () => {
    results.innerHTML = '';
    status.textContent = 'Search index could not be loaded. Try opening search-index.json directly from the navigation.';
  };

  const filterSummary = (state) => {
    const parts = [];
    if (state.q) parts.push(`text “${state.q}”`);
    if (state.asset) parts.push(`asset ${state.asset}`);
    if (state.dataQuality) parts.push(`data quality ${state.dataQuality.replace('_', ' ')}`);
    if (state.trendConfidence) parts.push(`trend confidence ${state.trendConfidence.replace('_', ' ')}`);
    if (state.dateFrom || state.dateTo) parts.push(`date ${state.dateFrom || 'start'} to ${state.dateTo || 'latest'}`);
    return parts.join(', ');
  };

  const metadataChips = (item) => {
    const chips = [];
    asArray(item.assets).slice(0, 6).forEach((asset) => chips.push(`<span>${asset}</span>`));
    if (item.trend_confidence_bucket) chips.push(`<span>Trend: ${String(item.trend_confidence_bucket).replace('_', ' ')}</span>`);
    if (item.data_quality_status) chips.push(`<span>Data: ${String(item.data_quality_status).replace('_', ' ')}</span>`);
    if (item.report_date) chips.push(`<span>${item.report_date}</span>`);
    return chips.length ? `<div class="search-result-chips">${chips.join('')}</div>` : '';
  };

  const renderResults = () => {
    if (loadFailed) {
      renderFailure();
      return;
    }

    const state = filters();
    updateUrl(state);

    if (!hasActiveFilters(state)) {
      renderEmpty();
      return;
    }

    const matches = index.filter((item) => filterItem(item, state)).slice(0, 50);
    const summary = filterSummary(state);

    status.textContent = matches.length
      ? `${matches.length} result${matches.length === 1 ? '' : 's'} for ${summary}.`
      : `No archived reports matched ${summary}.`;

    if (!matches.length) {
      results.innerHTML = '<p class="muted">Try removing a filter, broadening the date range, or searching for BTC, ETH, SOL, ETF, liquidation, or a date like 2026-05-11.</p>';
      return;
    }

    results.innerHTML = matches.map((item) => {
      const sourceNames = asArray(item.structured_source_names).length ? item.structured_source_names : item.sources;
      const sourceSummary = asArray(sourceNames).length
        ? `<p class="search-card-sources"><strong>Sources:</strong> ${asArray(sourceNames).slice(0, 4).map((source) => highlight(source, state.q)).join('; ')}</p>`
        : '';
      return `
        <article class="search-result-card">
          <div class="eyebrow">${item.timestamp || 'Timestamp unavailable'}</div>
          <h3><a href="${item.url}">${highlight(item.title || 'Untitled report', state.q)}</a></h3>
          ${metadataChips(item)}
          <p>${highlight(item.headline || 'No headline available.', state.q)}</p>
          <p class="search-card-path">${highlight(item.path || '', state.q)}</p>
          ${sourceSummary}
          <a class="text-link" href="${item.url}">Open report →</a>
        </article>`;
    }).join('');
  };

  const setQuery = (query) => {
    if (input) input.value = query;
    renderResults();
  };

  const applyInitialState = () => {
    const params = new URLSearchParams(window.location.search);
    if (input) input.value = params.get('q') || '';
    if (assetFilter) assetFilter.value = params.get('asset') || '';
    if (dataQualityFilter) dataQualityFilter.value = params.get('data_quality') || '';
    if (trendConfidenceFilter) trendConfidenceFilter.value = params.get('trend_confidence') || '';
    if (dateFromFilter) dateFromFilter.value = params.get('date_from') || '';
    if (dateToFilter) dateToFilter.value = params.get('date_to') || '';
  };

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    renderResults();
  });

  input?.addEventListener('input', renderResults);
  [assetFilter, dataQualityFilter, trendConfidenceFilter, dateFromFilter, dateToFilter]
    .forEach((control) => control?.addEventListener('change', renderResults));

  clearFilters?.addEventListener('click', () => {
    if (input) input.value = '';
    if (assetFilter) assetFilter.value = '';
    if (dataQualityFilter) dataQualityFilter.value = '';
    if (trendConfidenceFilter) trendConfidenceFilter.value = '';
    if (dateFromFilter) dateFromFilter.value = '';
    if (dateToFilter) dateToFilter.value = '';
    renderResults();
  });

  suggestions.forEach((button) => {
    button.addEventListener('click', () => setQuery(button.dataset.searchSuggestion || ''));
  });

  fetch('search-index.json')
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      index = Array.isArray(data) ? data : [];
      applyInitialState();
      renderResults();
    })
    .catch(() => {
      loadFailed = true;
      renderFailure();
    });
})();
