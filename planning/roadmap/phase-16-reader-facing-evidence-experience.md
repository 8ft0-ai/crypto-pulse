# Phase 16 — Reader-facing evidence experience

Status: selected roadmap direction; implementation not yet authorised.

This forward-looking roadmap spec promotes the freshly approved reconciled `reader-facing-evidence-experience/v1` design from #498/#497 as the bounded CryptoPulse successor direction after Phase 15. It improves how readers understand existing repository-owned evidence without changing the frozen Phase 13/15 evidence contracts, activating Phase 14 publication, promoting #477, or introducing new model/provider or trading-oriented behaviour.

## Governance

```text
Primary shaping issue: #498
Complementary temporal shaping issue: #497
Approved site-wide source design: #498 comment 5383631194 — reader-facing-market-evidence/v1.3
Site-wide design approval: #498 comment 5383679379
Approved temporal source design: #497 comment 5383794333 — reader-facing-temporal-evidence/v1.2
Temporal design approval: #497 comment 5383815247
Reconciled design: #498 comment 5383837157 — reader-facing-evidence-experience/v1
Fresh reconciliation approval: #498 comment 5383876093 — APPROVED
Owner successor/promotion authority: #498 comment 5383907281 — ACCEPT
Roadmap-promotion issue: #499
Trusted promotion baseline: f84d6166f0aa32cb9f50ddfcfb33317b975fb152
```

The roadmap-promotion candidate is planning-only. A parent Phase 16 delivery-control issue is created only after this roadmap candidate is freshly reviewed and separately authorised for merge.

## Problem statement

CryptoPulse already holds useful deterministic market evidence, preserved historical reports and one public Phase 15 temporal-evidence surface, but the main reader path remains assurance-oriented rather than reader-oriented.

The current site can conflate several distinct authorities:

- report chronology;
- the newest valid Phase 13 observation in the exact checked-out repository state;
- report narrative/citations;
- repository-owned source evidence;
- the existing Phase 15 temporal series.

The current report ordering also has a concrete chronology defect for the retained deterministic July reports: the historical filename sort can place `1742_AEST.md` ahead of `2031_AEST.md` even though the latter is later. The temporal renderer can also present synthetic zero extrema when the 24-slot series contains no asserted numeric values. Archive language can imply continuous hourly coverage even when the retained corpus is discontinuous.

Phase 16 exists to make the public site reader-first while preserving evidence before intelligence, exact provenance, explicit missingness/degradation and the AI-demo/non-advice boundary.

## Goal

Deliver and prove the smallest coherent reader-facing experience that:

- establishes one canonical report chronology across retained report generations before any `latest_report` claim;
- resolves one shared reader-evidence context for Home and `latest.html`;
- keeps `latest_report`, `current_observation` and the existing Phase 15 temporal series as distinct authorities;
- shows deterministic point-in-time market values only from the exact validated current observation in the immutable checked-out commit;
- keeps report title/headline/body/citations/generation metadata bound to the canonical latest report;
- presents safe `Most recent available` / `Historical` wording without implying live/current status;
- makes source health, deterministic-vs-AI semantics, report citations and underlying data provenance understandable before deep audit detail;
- fixes the reader projection of the existing Phase 15 BTC temporal surface without changing its evidence contract;
- gives Archive canonical reverse chronology, truthful coverage/discontinuity semantics and bounded deterministic filtering across heterogeneous report generations;
- leaves sparse evidence sparse rather than inventing history or activating a new accumulation/publication mechanism.

## Frozen Phase 16 product contract

```text
reader-facing-evidence-experience/v1
```

The contract is an information-authority and presentation contract. It does not create a new market-data, temporal-evidence, publication or model authority.

## Canonical reader authority model

### Canonical report chronology

Phase 16 must introduce one canonical report chronology resolver used by every report-recency consumer.

For retained deterministic reports:

- use validated `generated_at_utc` as canonical report time;
- require local/timezone/path evidence to be consistent with that time where present;
- do not repair contradictory deterministic metadata from a filename;
- fail closed when the retained deterministic report cannot be ordered safely.

For retained legacy reports:

- prefer a validated front-matter `timestamp` when present;
- permit the recognised legacy path/timezone fallback only when that metadata is absent;
- fail closed on timestamp/path conflict;
- fail closed on unsupported or unorderable retained report chronology rather than silently skipping a possibly newer report.

Across the successfully resolved chronology population:

```text
latest_report = maximum unique report_time_utc
```

Duplicate exact canonical report instants fail closed rather than electing a lexical/path winner.

The supplied current-corpus regression is normative: with the retained `1742_AEST.md` and `2031_AEST.md` front-matter/path shapes, `2031_AEST.md` must sort first, become `latest_report`, and display the 20:31 AEST instant rather than a date-only fallback.

### `latest_report`

`latest_report` authorises only report-specific material:

- report title/headline/body;
- validated report display timestamp and URL;
- report citations;
- report-generation/evidence-format classification;
- archive/report navigation and report-centric machine-output ordering where already applicable.

It does not authorise point-in-time deterministic market values for another observation.

### `current_observation`

`current_observation` is resolved independently from the exact immutable checked-out repository state using the frozen Phase 13 participation/ordering boundary.

It is anchored at the maximum canonical participating observation hour. If the newest participating observation population is malformed, ambiguous, invalid or otherwise unresolvable under the governing evidence rules, reader resolution fails closed for `current_observation`; it must not silently fall back to an older hour merely to keep cards visible.

When the current point observation itself is valid but its predecessor/comparison evidence is unavailable, the validated point observation may still be shown while temporal comparison remains unavailable.

`current_observation` authorises only deterministic point-in-time fields actually supported by that exact validated snapshot, including the existing bounded BTC/ETH/SOL market evidence, source/evidence health and exact repository provenance represented by the governed source record.

### One shared reader-evidence context

Home and `latest.html` must consume one shared resolver, conceptually:

```text
repository_context
canonical_report_chronology
latest_report
current_observation
report_observation_relation
```

`report_observation_relation` is not a third authority. A report is related to the selected observation only when the report's governed `source_snapshot` path exactly equals the selected observation path. Do not infer a relation from date proximity, values or narrative text.

When the identities differ:

- Home and the primary `latest.html` reader summary use only `current_observation` for deterministic market cards, evidence time, source health and point-in-time provenance;
- `latest_report` is shown separately as `Most recent archived report` with its own timestamp and report-generation/evidence semantics;
- no report content or citation state is copied onto the newer observation;
- no newer observation values are inserted into the older report card;
- no report attachment is implied without exact `source_snapshot` path equality.

When no usable `current_observation` exists but `latest_report` does, show the report as historical content and explicitly omit deterministic observation cards rather than falling back to an older observation silently.

## Reader-facing surface roles

### Home

Home is the product-orientation and best-available-evidence surface. Its primary hierarchy is:

1. product identity plus compact pre-claim AI-generated-demo/non-advice notice;
2. most recent validated repository observation timestamp/status, or explicit unavailable state;
3. deterministic market cards/table from that observation when supported;
4. evidence-health/source-coverage summary;
5. concise deterministic-vs-AI explanation;
6. separate `Most recent archived report` summary/link when available;
7. ordinary reader links to `Most recent` and `Archive`;
8. one low-prominence Temporal evidence discovery link only when `temporal.html` succeeds from the same checked-out commit, preserving Phase 15;
9. `Inspect the evidence` detail below primary reader content.

### `latest.html`

Keep the URL for compatibility, but present it as **Most recent available market evidence** rather than a claim of live/current market data.

It consumes the same reader-evidence context as Home. Deterministic point values, evidence timestamp, source health and provenance come only from `current_observation`. The latest archived report remains a distinct historical/report object even when it is displayed on the same page.

### Archive

Archive is the preserved-history browsing surface. It must:

- use canonical reverse report chronology and canonical display timestamps;
- show report count and retained range truthfully;
- distinguish nominal generation cadence from actual retained coverage/discontinuity;
- expose deterministic report/evidence generation type and evidence state only where governed deterministic classification exists;
- keep historical report types visibly heterogeneous rather than normalising legacy/partial AI reports into deterministic snapshots;
- provide bounded reader filters at minimum for date/month, generation type and evidence state where deterministically classifiable;
- not infer asset membership from free text;
- place reader search/filter controls ahead of developer `search-index.json` access;
- omit or mark unavailable fields that are not comparable across report generations.

RSS, manifest and search-index remain report/archive-oriented unless separately governed. Existing schemas are not silently redefined to mean `current_observation`, but any report-recency ordering they already expose must consume canonical report chronology rather than a separate filename/path sort.

### Temporal evidence

The Phase 15 public authority remains exactly:

```text
series_kind: metric
series_key: BTC.price_usd
window_slots: 24 canonical UTC hours
public_page: temporal.html
homepage_discovery: one low-prominence link only when same-commit page generation succeeds
```

Phase 16 changes reader projection/presentation only. It introduces no new temporal series identity, stablecoin aggregate series, BTC-share series, additional metric/source series or derived temporal metric contract.

## Freshness semantics

Repository recency and market currentness remain separate concepts.

Safe Phase 16 language is:

- `Most recent validated repository observation` / `Most recent available observation` for `current_observation`;
- `Most recent archived report` for `latest_report`;
- `Historical` for archive/report context.

Do not persist `live`, `current`, `recent`, `up to date` or automatically ageing `X hours old` claims under the current static/inert publication boundary. Future `current`, `delayed` or `stale` classifications require a separately reviewed trustworthy freshness/publication contract and are not part of this phase.

## Evidence taxonomy, attribution and safety

The public experience must make these distinctions understandable without requiring knowledge of generator internals:

- **deterministic repository-backed evidence** — exact values/status derived under repository-owned validation rules;
- **AI-generated historical report content** — archived narrative/report material that may be inaccurate, incomplete, stale, misleading or hallucinated;
- **legacy / partial historical evidence** — retained older formats whose semantics are not equivalent to current deterministic snapshots;
- **generated static HTML** — deterministic presentation output with no new model inference during site build.

Report citations and underlying data provenance are separate concepts. Reader-facing labels must not say or imply that a report is simultaneously sourced and unsourced merely because it lacks embedded report citations while its underlying snapshot has repository provenance.

Before market claims, the site must identify the AI-generated-demo context and preserve that content is not financial advice, investment research, a recommendation, a trading signal or a basis for trading/investing/risk decisions. Context-specific caveats remain concise and the footer retains the safety meaning without overwhelming the main reader hierarchy.

## Temporal reader-state projection

Combined Slice 2 consumes only replay-valid same-commit Phase 15 evidence and preserves its frozen semantics.

The reader projection must expose at least:

```text
value_count
gap_count = 24 - value_count
exact gap reasons
degraded_value_count
continuous_pair_count
longest_continuous_run
```

`degraded_value_count` counts each asserted value once when either retained comparison side is `valid-degraded`.

`continuous_pair_count` counts only adjacent asserted values whose frozen continuity status is exactly `continuous`.

Presentation rules:

- `value_count == 0` means no chart and no synthetic min/max/extrema;
- isolated observations do not produce a line chart;
- a line chart is permitted only when `continuous_pair_count >= 1`;
- gaps/discontinuities are never bridged;
- no interpolation, smoothing, aggregation, backfill, carry-forward or trend inference;
- `BTC.price_usd` remains strictly positive under the frozen metric contract, so source zero remains invalid-metric gap evidence rather than a valid plotted value;
- zero participation still produces no `temporal.html` and therefore no Home discovery link.

The detailed 24-row evidence table and `Inspect the evidence` path remain available beneath the reader summary.

## Proposed implementation slices

The approved order is deliberate and must remain bounded to these three combined slices.

### Combined Slice 1 — canonical reader authority + Home / Most recent

Implement first:

- canonical `resolve_report_chronology(...)` across retained report generations;
- one `resolve_reader_evidence_context(...)` consuming canonical report chronology plus exact-commit Phase 13 observation resolution;
- `latest_report` / `current_observation` field-authority and exact relation rules;
- corrected report display timestamps;
- shared evidence taxonomy and safe most-recent wording;
- deterministic observation-backed market summary;
- report-citation versus underlying-provenance distinction;
- compact pre-claim safety hierarchy and progressive disclosure;
- preservation of the existing conditional low-prominence Phase 15 discovery link.

The chronology repair is part of Slice 1 because Home and `latest.html` must not call a report `most recent` using the known-wrong legacy sort.

### Combined Slice 2 — temporal reader-state projection + presentation

Implement second, consuming the shared taxonomy/safety/progressive-disclosure patterns from Slice 1:

- reader-state projection over replay-valid Phase 15 evidence;
- coverage/gap/degradation/continuity summary;
- corrected chart/no-chart and empty-domain behaviour;
- simple complete 24-row reader table;
- deeper evidence inspection;
- same-commit/fail-closed integration;
- unchanged conditional low-prominence discovery.

### Combined Slice 3 — Archive reader model + navigation integration

Implement third using the established chronology/taxonomy:

- canonical reverse chronology and archive range;
- actual coverage/discontinuity semantics;
- mixed report-generation/evidence taxonomy;
- deterministic card-field rules and unavailable-state handling;
- bounded reader search/filter hierarchy;
- developer-output demotion into the deeper technical layer;
- navigation integration across Home, Most recent, Temporal evidence and Archive.

## Explicitly excluded T2 evidence accumulation

#497 T2 source-evidence accumulation/promotion is not part of Phase 16.

Phase 16 must remain truthful under sparse evidence. It may not create or reuse mutable rolling-branch public authority, automatic source-evidence promotion, recurring publication activation, new retention policy, historical backfill or other evidence-accumulation machinery merely to improve charts or freshness.

Any later T2 design requires separate shaping, fresh review and owner authority.

## Non-goals

Phase 16 does not authorise:

- Phase 14 `pilot` or `recurring` activation;
- #477 work or promotion;
- deterministic-publication candidate generation/merge automation;
- mutable rolling branches as public rendering authority;
- any change to frozen Phase 10/11/12/13 contracts or `phase15-public-temporal-evidence/v1`;
- new external data sources or providers;
- model invocation, model/provider selection or credentials;
- new temporal series, derived metrics or broader temporal analytics;
- prediction, forecast, recommendation, sentiment call, trading signal, technical levels, targets, watchlists or personalised guidance;
- historical report/source mutation or backfill;
- committed generated `_site/` output;
- direct rewriting of archived report bodies;
- Pages permission, deployment or publication-authority redesign.

## Acceptance gates

Phase 16 implementation is complete only when all applicable gates are proved through exact-head validation and fresh independent review:

- [ ] Every report-recency consumer uses one canonical report chronology resolver.
- [ ] Deterministic report chronology validates `generated_at_utc` and consistency evidence and never repairs contradictory metadata from filenames.
- [ ] Legacy chronology prefers validated front-matter timestamp, uses recognised fallback only when allowed, and fails closed on conflicts/unorderable retained reports.
- [ ] Duplicate exact canonical report instants fail closed.
- [ ] The normative `1742_AEST.md` / `2031_AEST.md` regression selects and displays `2031_AEST.md` first at 20:31 AEST.
- [ ] Home and `latest.html` consume one shared reader-evidence context and cannot independently elect different observations.
- [ ] `current_observation` is anchored at the maximum canonical Phase 13 participating observation hour in the exact checked-out commit.
- [ ] Malformed/ambiguous/invalid newest participating observation fails closed with no older-observation fallback.
- [ ] Point-observation validity remains distinct from predecessor/temporal-comparison availability.
- [ ] A deterministic mismatch fixture where `latest_report != current_observation` proves values/timestamp/status/provenance remain observation-bound and title/headline/body/citations/link remain report-bound.
- [ ] A matching fixture proves report/observation association only by exact governed `source_snapshot` path equality.
- [ ] A no-usable-observation + existing-report fixture shows report-only fallback without deterministic observation cards.
- [ ] Exact evidence timestamp and pre-claim demo/non-advice framing appear before primary market values.
- [ ] Report citations and underlying data provenance remain visibly distinct.
- [ ] Archive uses canonical reverse chronology and reports actual retained coverage/discontinuity rather than implying continuous hourly coverage.
- [ ] Archive filters/classifications are deterministic and do not infer asset membership from free text.
- [ ] Phase 15 temporal authority remains one same-commit `BTC.price_usd` 24-slot record and one conditional low-prominence discovery link.
- [ ] Temporal projection proves truthful `value_count`, gap reasons, degradation and continuity counts.
- [ ] `value_count == 0` emits no chart and no synthetic zero extrema.
- [ ] A line chart is emitted only with at least one exact continuous pair; no gap is bridged.
- [ ] No interpolation, smoothing, aggregation, backfill, carry-forward or trend inference is introduced.
- [ ] Zero Phase 15 participation still removes both `temporal.html` and its Home link.
- [ ] #497 T2, Phase 14 activation and #477 remain untouched.
- [ ] Generated `_site/` remains disposable and uncommitted.
- [ ] Same repository input produces deterministic generated output under the existing build contract.

## Risks and mitigations

### Risk: report recency and observation recency are conflated

Mitigation: canonical report chronology and Phase 13 observation resolution remain separate authorities inside one shared reader context; exact source-snapshot equality is the only report/observation relation.

### Risk: presentation silently repairs missing or sparse evidence

Mitigation: fail closed on unusable current evidence, omit unsupported cards/charts, preserve gaps and discontinuities, and exclude T2 accumulation from this phase.

### Risk: the UX overstates freshness

Mitigation: use repository-recency language only and prohibit live/current/recent/up-to-date claims without a separately governed trustworthy freshness contract.

### Risk: historical report generations appear falsely comparable

Mitigation: explicit deterministic/AI-generated/legacy taxonomy, bounded card fields and unavailable states instead of forced normalisation.

### Risk: temporal presentation changes the Phase 15 evidence meaning

Mitigation: reader projection consumes only replay-valid Phase 15 records and preserves exact 24-slot, continuity, gap, positivity and same-commit semantics.

### Risk: reader-first presentation weakens safety or provenance

Mitigation: keep concise pre-claim demo/non-advice meaning, preserve exact evidence timestamps/status/provenance and retain deeper `Inspect the evidence` detail.

### Risk: Phase 16 becomes an implicit publication or accumulation phase

Mitigation: Phase 14/#477 and #497 T2 are explicit non-goals; no mutable branch, recurring activation, backfill or evidence-promotion authority is introduced.

## Definition of done

The phase is complete when:

- [ ] the parent Phase 16 issue and linked issues for the three combined slices exist after roadmap promotion is merged;
- [ ] each implementation candidate receives exact-head repository validation and genuinely fresh independent substantive review before merge;
- [ ] the three combined slices are delivered in the approved dependency order or an independently reviewed equivalent preserves all authority boundaries;
- [ ] user-facing and repository acceptance fixtures prove chronology, authority separation, temporal sparse-data semantics, safety and provenance boundaries;
- [ ] the public Pages result is verified after the final authorised site-affecting merge using exact merged/deployed identity evidence;
- [ ] `planning/delivery/phase-16-reader-facing-evidence-experience.md` records what actually shipped and what remains excluded;
- [ ] `planning/delivery-log.md`, `planning/delivery/delivery.yaml` and regenerated `planning/delivery/graph.md` are updated at close-out as applicable;
- [ ] roadmap state is updated at close-out without implicitly selecting another successor;
- [ ] generated `_site/` output is not committed.

## Follow-on delivery record

At close-out, create:

```text
planning/delivery/phase-16-reader-facing-evidence-experience.md
```

No follow-on T2 evidence accumulation, Phase 14/#477 operationalisation, additional temporal series, model/provider work or trading-oriented capability is implied by Phase 16 completion.