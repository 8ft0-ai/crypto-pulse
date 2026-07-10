# Phase 4 — Live-site provenance UX

Status: shaping.

This is a forward-looking roadmap spec. It describes intended work before delivery. After the phase is delivered, close-out evidence should move into `planning/delivery/` as a completed delivery record.

## Problem statement

The live CryptoPulse site now has a working static publishing path, but the presentation layer is not yet showing the strongest part of the system.

The source/provenance machinery is credible: reports can point back to a source snapshot, source quality status, per-source `ok` / `skipped` / reason details, exchange cross-check strategy, validation boundaries, deterministic generation, and explicit scope limitations. That is the product's real trust story.

The homepage and report pages currently risk underselling that work. Older and newer report formats expose different fields, and the homepage extractor can surface placeholders such as `Not specified in archived report` for fields that newer deterministic reports no longer intend to provide. Boilerplate disclaimer text can also be extracted as headline or interpretation copy, which makes the most visible report surfaces look like legal warnings rather than structured output.

Phase 4 should correct the live-site information design so the site leads with provenance, evidence, and schema-aware rendering rather than repeated disclaimers and empty-looking fields.

## Goal

Make the live site read as an auditable automated publishing demo.

The primary outcome is a homepage, latest-report page, and archive preview experience that foregrounds source provenance and generation boundaries while suppressing misleading placeholders, duplicate disclaimer copy, and unstable summary fields.

## Non-goals

Phase 4 should not introduce:

```text
No source-ingestion redesign.
No generated report data-model rewrite.
No change to the deterministic report proof model.
No LLM-generated report narrative.
No investment advice, trading recommendations, trading signals, target prices, or position guidance.
No auto-merge.
No auto-publish change beyond the existing GitHub Pages workflow.
No secrets or paid API keys.
No committed _site output.
```

This is a presentation-layer and information-design phase. It should preserve the current source-of-truth model: raw Markdown reports and archived source snapshots remain the authored evidence; `_site/` remains disposable generated output.

## Target state

The site should make the provenance system obvious before a technical reader has to scroll into report footers.

```text
hero / intro explains this is an auditable automated publishing demo
homepage latest card shows only fields actually available for the report format
homepage avoids per-field apology text for missing retired fields
headline and interpretation extractors ignore disclaimer/product-boundary boilerplate
report page surfaces source snapshot quality, source status, cross-check strategy, and generation boundaries near the top
full audit detail remains available deeper in the report
archive cards show date + time and stable scan-friendly metric slots
only one prominent disclaimer treatment appears per surface, with lighter footer reinforcement
```

## Acceptance gates

Phase 4 is complete when:

- [ ] the homepage latest summary is schema-aware and hides unavailable fields instead of rendering repeated placeholder text;
- [ ] disclaimer/product-boundary boilerplate is not used as the latest headline, analyst interpretation, or primary summary copy;
- [ ] the homepage information hierarchy leads with what the demo proves and then allows uninterrupted report/archive scanning;
- [ ] duplicate CTAs to the same latest-report URL are reduced or clearly prioritised;
- [ ] report pages surface provenance and generation-boundary information higher in the reading flow;
- [ ] repeated disclaimer blocks are consolidated into one prominent treatment plus concise reinforcement where needed;
- [ ] archive preview cards show hourly time as well as date;
- [ ] archive preview cards use stable metric slots or omit missing values rather than swapping vocabulary unpredictably;
- [ ] source-quality and source-status details remain available and traceable;
- [ ] accessibility is preserved, including skip link, semantic headings, non-colour signals for status/positive/negative values, and readable mobile layout;
- [ ] `python -m site_generator` still builds the site;
- [ ] PR validation passes;
- [ ] generated `_site/` output is not committed.

## Proposed implementation slices

Use linked issues rather than relying on native GitHub sub-issues.

```text
1. Parent Phase 4 issue — Live-site provenance UX.
2. Fix homepage extracted-summary rendering.
3. Rework homepage information hierarchy and CTA priority.
4. Improve report-page provenance layout and disclaimer treatment.
5. Stabilise archive preview cards for hourly scanning.
6. Prove Phase 4 on the live site and record close-out evidence.
```

## Risks and mitigations

### Risk: The site becomes less clear about regulatory/product boundaries

Mitigation: keep one strong canonical disclaimer treatment on each major surface and preserve footer reinforcement. Remove only duplicate and extractor-generated disclaimer stutter.

### Risk: Schema-aware rendering hides useful information

Mitigation: hide unavailable fields only when the source report format does not provide them. Preserve fields that are available and add a compact report-format note where it improves clarity.

### Risk: Provenance detail overwhelms non-technical readers

Mitigation: use a layered information design: short provenance summary near the top, full evidence/source-status detail deeper in the report.

### Risk: Archive cards become too rigid across report versions

Mitigation: define a stable preferred metric order, then omit unavailable values rather than substituting unrelated fields or apology text.

### Risk: Implementation drifts into report generation or source ingestion changes

Mitigation: keep Phase 4 scoped to site generation, extraction, rendering, styling, and accessibility. Do not change source snapshots, report content, workflow identity, or publication model.

## Definition of done

The phase is complete when:

- [ ] the parent Phase 4 issue and linked child issues exist;
- [ ] implementation PRs are merged;
- [ ] the live site has been smoke-tested at `https://8ft0-ai.github.io/crypto-pulse/`;
- [ ] homepage, latest report, archive, and search surfaces are checked;
- [ ] proof evidence records screenshots or textual observations from the live site where practical;
- [ ] close-out evidence is added to the parent issue;
- [ ] a delivery record is added under `planning/delivery/`;
- [ ] `planning/delivery-log.md` is updated;
- [ ] `planning/delivery/delivery.yaml` is updated, or explicitly marked not applicable;
- [ ] `planning/delivery/graph.md` is regenerated when `delivery.yaml` changes;
- [ ] generated `_site/` output is not committed.

## Close-out PR checklist

For the PR that closes this phase:

- [ ] Update `planning/delivery/phase-04-live-site-provenance-ux.md`.
- [ ] Update `planning/delivery-log.md`.
- [ ] Update `planning/delivery/delivery.yaml`.
- [ ] Regenerate `planning/delivery/graph.md`.
- [ ] Update `planning/roadmap/` only if roadmap intent or next-phase direction changed.
- [ ] Confirm raw Markdown reports remain the source of truth.
- [ ] Confirm generated `_site/` output is not committed.

## Follow-on delivery record

At close-out, create:

```text
planning/delivery/phase-04-live-site-provenance-ux.md
```

The completed delivery record should explain what changed in the live-site presentation layer, what proof evidence was used, what UX risks were reduced, and what boundaries were preserved.
