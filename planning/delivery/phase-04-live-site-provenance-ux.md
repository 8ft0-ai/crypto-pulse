# Phase 4 — Live-site provenance UX

Status: implementation complete; public live-site fetch requires external confirmation.

## Outcome

Phase 4 made CryptoPulse present its strongest product property — auditable automated publishing — before market commentary. Homepage and report rendering are now schema-aware, provenance-led, and less repetitive, while archive cards are easier to scan as an hourly record.

## Delivery scope

Parent issue: #160  
Close-out issue: #165  
Implementation issues: #161, #163, #162, #164  
Implementation PRs: #166, #167, #168, #169

```text
#161 / PR #166 — schema-aware homepage summary rendering
Merge commit: 70cfcf64ea93427c13c6442d21397df04378d8e2
Validation run: 29081901945

#163 / PR #167 — provenance-first report-page layout
Merge commit: dfaf8b61a5a4538e9c83364dfc1aa1f11726a8c1
Validation run: 29082778088

#162 / PR #168 — homepage hierarchy and CTA priority
Merge commit: 1a1e04412bd330be4115ea15bcea852b85f33ffc
Validation run: 29083425572

#164 / PR #169 — stable hourly archive cards
Merge commit: f73fca68667f5f15794e7e06d97222d444a9720e
Validation run: 29084860287
```

## Smoke-test evidence

### Homepage

Generated-site tests and PR validation prove that:

- disclaimer and product-boundary boilerplate are excluded from headline and analyst-summary fields;
- retired fields are omitted rather than repeated as `Not specified` placeholders;
- demo purpose, provenance and pipeline explanation appear before report/archive scanning;
- the latest-report action has a clear primary role;
- archive previews show stable, schema-aware metrics.

### Latest report

Generated-site tests and PR validation prove that:

- source quality and provenance appear before the extracted summary and full report body;
- generation boundaries state that the static build makes no LLM calls, performs no hidden enrichment, and does not commit `_site/`;
- repeated warning treatments are consolidated;
- full report and structured source/audit detail remain available.

### Archive

Generated-site tests and PR validation prove that:

- cards show date plus `HH:MM` and timezone where available;
- preferred metric order is BTC change, ETH change, then data status;
- missing metrics are omitted;
- direction and status use labels and signs rather than colour alone;
- legacy and deterministic report formats remain linked.

### Search

The search page was not structurally changed in Phase 4. Shared navigation, stylesheet and accessibility build stages continue to include it, and the canonical build remains covered by PR validation.

## Accessibility checks

The generated-site build preserves:

- skip-link insertion;
- semantic heading structure checks in focused rendering tests;
- visible keyboard focus treatment for links and buttons;
- responsive single-column CTA treatment on smaller screens;
- textual `Up`, `Down`, `Change` and `Status` signals in archive cards.

## Public live-site check

Configured live URL: `https://8ft0-ai.github.io/crypto-pulse/`

A direct fetch of the homepage, latest report, archive and search pages was attempted during close-out. The execution environment could not resolve the GitHub Pages host and the browser fetch path returned a cache/safety failure. No successful public HTTP response was available to cite from this run.

This is an evidence limitation, not a claimed pass. The implementation is proven through focused tests and successful `Validate CryptoPulse PR` runs, but issue #165 and parent #160 should only be closed after a successful external browser check of the deployed Pages site.

## Boundaries preserved

- Raw Markdown reports remain the source of truth.
- `_site/` remains generated and uncommitted.
- No source snapshots or generated reports were edited.
- No ingestion, workflow or runtime changes were introduced.
- No LLM-generated market narrative was added.
- No investment advice, recommendation, target price, signal or position guidance was added.

## Delivery graph decision

Delivery graph update: N/A.

Phase 4 changes presentation and rendering of already-modelled report and provenance artefacts. It does not add a new causal pipeline stage, production artefact or operating-model decision. Under the repository’s compact graph-modelling rules, adding all four UX PRs would create an implementation inventory rather than improve causal navigation. The phase remains recorded in this delivery record and `planning/delivery-log.md`.

## Remaining close condition

Run a successful external browser smoke test against the configured GitHub Pages URL for homepage, latest report, archive and search. Once confirmed, add the evidence to #165 and #160, then close both issues.