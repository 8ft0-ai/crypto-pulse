(() => {
  "use strict";

  const controls = document.querySelector("[data-archive-filter-controls]");
  if (!controls) {
    return;
  }

  const cards = Array.from(document.querySelectorAll(".archive-card"));
  const selects = Array.from(controls.querySelectorAll("[data-archive-filter]"));
  const reset = controls.querySelector("[data-archive-filter-reset]");
  const status = controls.querySelector("[data-archive-result-count]");

  const selected = (name) => {
    const element = controls.querySelector(`[data-archive-filter="${name}"]`);
    return element ? element.value : "";
  };

  const cardMatches = (card) => {
    const month = selected("month");
    const generation = selected("generation");
    const evidence = selected("evidence");

    return (!month || card.dataset.archiveMonth === month)
      && (!generation || card.dataset.archiveGeneration === generation)
      && (!evidence || card.dataset.archiveEvidenceState === evidence);
  };

  const updateContainerVisibility = () => {
    for (const selector of [".archive-day", ".archive-month", ".archive-year"]) {
      for (const container of document.querySelectorAll(selector)) {
        const visible = Array.from(container.querySelectorAll(".archive-card"))
          .some((card) => !card.hidden);
        container.hidden = !visible;
      }
    }
  };

  const applyFilters = () => {
    let visibleCount = 0;
    for (const card of cards) {
      card.hidden = !cardMatches(card);
      if (!card.hidden) {
        visibleCount += 1;
      }
    }
    updateContainerVisibility();
    if (status) {
      status.textContent = `${visibleCount} of ${cards.length} retained reports shown`;
    }
  };

  controls.hidden = false;
  for (const select of selects) {
    select.addEventListener("change", applyFilters);
  }

  if (reset) {
    reset.addEventListener("click", () => {
      for (const select of selects) {
        select.value = "";
      }
      applyFilters();
    });
  }

  applyFilters();
})();
