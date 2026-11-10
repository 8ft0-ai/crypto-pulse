(function () {
  var reportBodies = document.querySelectorAll('.report-body');

  reportBodies.forEach(function (body) {
    body.querySelectorAll('table').forEach(function (table) {
      if (table.closest('.table-scroll-wrap')) return;

      var wrapper = document.createElement('div');
      wrapper.className = 'table-scroll-wrap';
      wrapper.setAttribute('tabindex', '0');
      wrapper.setAttribute('role', 'region');
      wrapper.setAttribute('aria-label', 'Scrollable report table');

      var hint = document.createElement('div');
      hint.className = 'table-scroll-hint';
      hint.textContent = 'Scroll sideways to view the full table';

      table.parentNode.insertBefore(hint, table);
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });

    body.querySelectorAll('h2').forEach(function (heading) {
      if (!heading.id && !heading.querySelector('span[id]')) return;
      if (heading.nextElementSibling && heading.nextElementSibling.className === 'report-section-actions') return;

      var sectionActions = document.createElement('div');
      sectionActions.className = 'report-section-actions';
      var link = document.createElement('a');
      link.className = 'back-to-top-link';
      link.href = '#top';
      link.textContent = 'Back to top ↑';
      sectionActions.appendChild(link);

      var next = heading.nextElementSibling;
      if (next && next.parentNode) {
        next.parentNode.insertBefore(sectionActions, next.nextSibling);
      }
    });
  });
})();
