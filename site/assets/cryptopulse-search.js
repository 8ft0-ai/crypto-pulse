(() => {
  const form = document.getElementById('search-form');
  const input = document.getElementById('search-query');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const suggestions = document.querySelectorAll('[data-search-suggestion]');

  let index = [];
  let loadFailed = false;

  const normalise = (value) => String(value || '').toLowerCase();

  const searchableText = (item) => [
    item.title,
    item.timestamp,
    item.headline,
    item.path,
    item.year,
    item.month,
    item.day,
    ...(Array.isArray(item.sources) ? item.sources : []),
  ].map(normalise).join(' ');

  const highlight = (text, query) => {
    const safeText = String(text || '');
    if (!query) return safeText;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return safeText.replace(new RegExp(`(${escaped})`, 'ig'), '<mark>$1</mark>');
  };

  const renderEmpty = () => {
    results.innerHTML = '';
    status.textContent = 'Enter a search term to explore archived demo reports.';
  };

  const renderFailure = () => {
    results.innerHTML = '';
    status.textContent = 'Search index could not be loaded. Try opening search-index.json directly from the navigation.';
  };

  const renderResults = (query) => {
    if (loadFailed) {
      renderFailure();
      return;
    }

    const trimmed = query.trim();
    if (!trimmed) {
      renderEmpty();
      return;
    }

    const terms = trimmed.toLowerCase().split(/\s+/).filter(Boolean);
    const matches = index
      .map((item) => ({ item, haystack: searchableText(item) }))
      .filter(({ haystack }) => terms.every((term) => haystack.includes(term)))
      .slice(0, 50)
      .map(({ item }) => item);

    status.textContent = matches.length
      ? `${matches.length} result${matches.length === 1 ? '' : 's'} for “${trimmed}”.`
      : `No archived reports matched “${trimmed}”.`;

    if (!matches.length) {
      results.innerHTML = '<p class="muted">Try a broader query such as BTC, ETH, SOL, ETF, liquidation, or a date like 2026-05-11.</p>';
      return;
    }

    results.innerHTML = matches.map((item) => {
      const sourceSummary = Array.isArray(item.sources) && item.sources.length
        ? `<p class="search-card-sources"><strong>Sources:</strong> ${item.sources.slice(0, 3).map((source) => highlight(source, trimmed)).join('; ')}</p>`
        : '';
      return `
        <article class="search-result-card">
          <div class="eyebrow">${item.timestamp || 'Timestamp unavailable'}</div>
          <h3><a href="${item.url}">${highlight(item.title || 'Untitled report', trimmed)}</a></h3>
          <p>${highlight(item.headline || 'No headline available.', trimmed)}</p>
          <p class="search-card-path">${highlight(item.path || '', trimmed)}</p>
          ${sourceSummary}
          <a class="text-link" href="${item.url}">Open report →</a>
        </article>`;
    }).join('');
  };

  const setQuery = (query) => {
    input.value = query;
    const url = new URL(window.location.href);
    if (query.trim()) {
      url.searchParams.set('q', query.trim());
    } else {
      url.searchParams.delete('q');
    }
    window.history.replaceState({}, '', url);
    renderResults(query);
  };

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    setQuery(input.value);
  });

  input?.addEventListener('input', () => {
    setQuery(input.value);
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
      const initialQuery = new URLSearchParams(window.location.search).get('q') || '';
      if (initialQuery) {
        input.value = initialQuery;
        renderResults(initialQuery);
      } else {
        status.textContent = `Loaded ${index.length} archived demo reports. Enter a search term to begin.`;
      }
    })
    .catch(() => {
      loadFailed = true;
      renderFailure();
    });
})();
