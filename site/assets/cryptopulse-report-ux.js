(() => {
  const reportBodies = document.querySelectorAll('.report-body');

  reportBodies.forEach((body) => {
    body.querySelectorAll('table').forEach((table) => {
      if (table.closest('.table-scroll-wrap')) return;
      const wrapper = document.createElement('div');
      wrapper.className = 'table-scroll-wrap';
      wrapper.setAttribute('tabindex', '0');
      wrapper.setAttribute('role', 'region');
      wrapper.setAttribute('aria-label', 'Scrollable report table');

      const hint = document.createElement('div');
      hint.className = 'table-scroll-hint';
      hint.textContent = 'Scroll sideways to view the full table';

      table.parentNode.insertBefore(hint, table);
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });

    body.querySelectorAll('h2[id], h2:has(span[id])').forEach((heading) => {
      const sectionActions = document.createElement('div');
      sectionActions.className = 'report-section-actions';
      sectionActions.innerHTML = '<a class="back-to-top-link" href="#top">Back to top ↑</a>';
      const next = heading.nextElementSibling;
      if (next) {
        next.parentNode.insertBefore(sectionActions, next.nextSibling);
      }
    });
  });
})();
