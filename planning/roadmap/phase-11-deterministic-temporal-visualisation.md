# Phase 11 — Deterministic temporal visualisation

Status: complete.

Shaping/design issue: #416

Frozen design proposal: comment `5304820349`

Trusted design base: `03ec37a3fa2aa08fabf021364dc46692dde85149`

Delivery control: #418

Close-out issue: #428

Delivery record: `planning/delivery/phase-11-deterministic-temporal-visualisation.md`

This roadmap specification records the now-completed `phase11-temporal-visualisation/v1` direction. Implementation was delivered through the separately governed four-slice plan on #418. Phase 11 remains an offline deterministic evidence/rendering capability; it does not authorise renderer/CSS changes in the public site, workflow changes, report/site integration, publication changes, provider/model use, source acquisition or generated `_site/` changes.

## Problem statement

Phase 10 now provides deterministic, repository-owned exact-hour comparison evidence, including immutable input identity, fail-closed predecessor resolution, metric/source evidence and explicit degraded quality. CryptoPulse still lacks a canonical way to inspect that evidence as temporal history without asking a renderer to infer continuity, fill gaps or read raw snapshots as an alternate success path.

A visual layer is useful only if it preserves the same auditability as the structured Phase 10 evidence. Missing or ambiguous hours must remain visible, `valid-degraded` evidence must remain attributable, source status must remain categorical, and rendered continuity must be proven from retained predecessor/current identity rather than inferred from adjacent timestamps.

## Goal

Prove a deterministic offline temporal evidence and rendering path that:

1. consumes only repository-owned evidence under the frozen Phase 10 contracts;
2. materialises one canonical `crypto-temporal-series/v1` record for an exact UTC hourly window;
3. preserves every slot as either an auditable value or explicit gap;
4. retains immutable Phase 10 comparison, current and predecessor provenance;
5. renders validated series records into deterministic accessible HTML plus inline SVG and a complete tabular equivalent;
6. reproduces byte-identical canonical series and renderer output from the same immutable evidence with zero provider/model/network calls.

The phase is successful when reviewers can audit temporal numeric or categorical source-status history without any interpolation, aggregation, smoothing, normalisation, inferred market values or raw-snapshot success bypass.

## Frozen design authority

Implementation planning must preserve the exact reviewed design in #416 comment `5304820349`:

```text
phase11-temporal-visualisation/v1
crypto-temporal-series/v1
crypto-snapshot-comparison/v1
phase10-predecessor-exact-hour/v1
phase10-snapshot-semantics-0.2/v1
```

Phase 11 does not alter the Phase 10 contracts. A Phase 11 validator must replay the existing Phase 10 comparison path against the immutable repository context rather than trusting an asserted `comparison_id`, value, identity or gap classification as proof.

## Authoritative evidence boundary

The series builder is given exactly one immutable repository commit/tree and an explicit inclusive UTC window.

Repository-owned hourly snapshot candidates are enumerated only to establish slot membership and choose the unique current candidate passed into Phase 10. Raw snapshot metrics are never a separate value-producing success path.

If any candidate within the immutable Phase 10 snapshot path boundary cannot yield a parseable authoritative `run.generated_at_utc` under the existing timestamp semantics, series construction fails closed before slot classification. An implementation must not silently skip such a candidate and then emit a misleading missing-slot result.

For each exact hourly slot:

```text
zero current candidates  -> current-missing
more than one candidate  -> current-ambiguous
exactly one candidate    -> replay existing Phase 10 comparison path
```

An ambiguous slot retains every competing immutable candidate identity in deterministic `(path, sha256)` order solely for canonical output; that order must never select a winner.

## Window and ordering

Phase 11 v1 accepts:

```text
start_utc: inclusive, exact UTC hour
end_utc: inclusive, exact UTC hour
maximum: 168 hourly slots
```

Invalid, non-hour-aligned, reversed or oversized windows fail closed before evidence processing.

Every hour in the inclusive window appears exactly once in strictly ascending UTC order. There is no slot compression, no fallback to an older snapshot and no widening of Phase 10's exact `3,600`-second predecessor rule.

## Numeric metric vocabulary

V1 numeric temporal series are limited to these exact current-side Phase 10 metric identities:

```text
BTC.price_usd
BTC.market_cap_usd
BTC.volume_24h_usd
ETH.price_usd
ETH.market_cap_usd
ETH.volume_24h_usd
SOL.price_usd
SOL.market_cap_usd
SOL.volume_24h_usd
defi.total_tvl_usd
USDT.circulating_usd
USDC.circulating_usd
```

The key-to-Phase-10 identity mapping is frozen:

- `BTC|ETH|SOL.<field>` -> family `market-asset`, named symbol and field;
- `defi.total_tvl_usd` -> family `defi-aggregate`, null symbol, field `total_tvl_usd`;
- `USDT|USDC.circulating_usd` -> family `stablecoin`, named symbol, field `circulating_usd`.

No alias discovery, cross-key aggregation or implementation-time vocabulary expansion is permitted.

Explicitly excluded from v1 visualisation even though some remain valid Phase 10 evidence:

```text
change_1h_pct
change_24h_pct
change_7d_pct
market_cap_rank
stablecoin price
```

## Source-status vocabulary

V1 source-status series are limited to the existing frozen source identities:

```text
coingecko
defillama
coinbase_exchange
kraken
okx
binance
bybit
cryptocompare
```

The only renderable current-side source statuses are:

```text
ok
warning
error
skipped
missing
```

Source status is categorical evidence. It must never be converted into a number, score, market movement, numeric axis or derived quality ranking.

## Value, gap and degraded semantics

A numeric slot is a value only when replayed Phase 10 evidence has:

```text
comparison_status == comparison-available
metric comparison_state == comparable
```

The emitted numeric value is the exact current-side Phase 10 evidence value. A raw snapshot read may not fill or replace it.

The complete v1 gap vocabulary is frozen as:

```text
current-missing
current-ambiguous
phase10-validation-contract-mismatch
phase10-current-invalid
phase10-current-identity-invalid
phase10-candidate-set-unorderable
phase10-predecessor-missing
phase10-predecessor-ambiguous
phase10-predecessor-invalid
phase10-predecessor-identity-invalid
phase10-predecessor-out-of-window
phase10-pair-schema-incompatible
phase10-pair-semantics-incompatible
phase10-comparison-ready
metric-unavailable-current
metric-unavailable-predecessor
metric-invalid-current
metric-invalid-predecessor
```

No other gap reason is valid in v1. Unknown/new Phase 10 statuses or metric states fail construction/validation closed instead of being coerced into a generic gap.

Per-slot classification precedence is frozen:

1. zero current candidates -> `current-missing`;
2. multiple current candidates -> `current-ambiguous` with complete sorted candidate identities;
3. one current candidate -> replay Phase 10;
4. any non-`comparison-available` Phase 10 status -> one-to-one `phase10-*` gap and stop classification for that slot;
5. numeric `comparison-available` -> `comparable` is a value, otherwise one-to-one supported `metric-*` gap;
6. source-status `comparison-available` -> emit the exact supported current-side categorical status.

A gap always breaks a numeric visual line. No point is carried forward across a gap.

Phase 11 preserves quality independently for both Phase 10 inputs. Each successful value entry retains the complete Phase 10 `current` and `predecessor` input records, including side-specific `quality_status` and `non_blocking_warnings`. A renderer may mark a point as degraded-backed when either side is `valid-degraded`, but it must not collapse or merge the two quality/warning records.

## No derived-data path

Phase 11 v1 permits none of the following:

```text
interpolation
resampling
aggregation
smoothing
moving averages
normalisation
index rebasing
percentage conversion
forecasting
carry-forward/back-fill
inferred values
```

Mapping exact numeric evidence to deterministic SVG coordinates is a display transform only. It is not new market evidence and must not be persisted as an analytical metric.

## Canonical `crypto-temporal-series/v1` record

A canonical series record must bind at minimum:

```text
schema_version
series_kind                  # metric | source-status
series_key                   # exact frozen key/identity
window.start_utc
window.end_utc
repository_context.commit_sha
repository_context.tree_sha
repository_context.validator.path/blob_sha
repository_context.config.path/blob_sha
phase10.comparison_schema_version
phase10.predecessor_policy_version
phase10.semantic_contract_version
entries[]                    # exactly one entry per hourly slot
series_id
```

Each entry has its exact UTC slot and exactly one of:

- `value`: exact numeric or categorical evidence, backing Phase 10 `comparison_id`, complete Phase 10 `current` input record and complete Phase 10 `predecessor` input record; or
- `gap`: one frozen v1 reason plus the exact audit evidence appropriate to that failure class.

`current-missing` records an empty candidate list. `current-ambiguous` records every competing immutable candidate identity. Phase-10-backed gaps retain the comparison identity/current/predecessor records exactly as available. Metric gaps retain successful comparison provenance plus the exact metric identity/state that caused the gap.

Snapshot identity reuses the Phase 10 repository-relative path, exact-byte SHA-256, schema version and canonical `run.generated_at_utc`; Phase 11 creates no alternate identity scheme.

`series_id` is the lowercase SHA-256 digest of canonical UTF-8 JSON for the complete record excluding `series_id`, using sorted keys, compact separators and `ensure_ascii=False`. No branch name, wall clock, filesystem metadata or process identity may enter canonical identity.

## Provenance and continuity

Every renderable value must trace to one exact replayed Phase 10 comparison plus exact current and predecessor snapshot identities under the immutable repository context.

A connected numeric line segment between adjacent value slots is permitted only when the later slot's retained Phase 10 predecessor input record is field-for-field identical to the earlier slot's retained Phase 10 current input record.

Otherwise the renderer breaks the line even when timestamps are adjacent.

The renderer makes this decision only from the already validated canonical series. It does not reopen snapshots, replay Phase 10 itself or infer continuity from timestamps or comparison hashes.

## Deterministic accessible rendering

Phase 11 remains offline. The proof renderer accepts only a validated `crypto-temporal-series/v1` record and emits deterministic reviewer-visible output consisting of:

```text
semantic HTML figure
inline SVG visualisation
figcaption
adjacent complete data table
```

No JavaScript, canvas, network resource or external asset is required.

The table is the complete non-visual equivalent and exposes every hourly slot, including timestamp, exact value/status or gap reason, current quality/warnings when available, predecessor quality/warnings when available, and concise comparison/current/predecessor provenance. Ambiguous slots expose all competing candidate identities.

Gap, degraded and source-status distinctions must not rely on colour alone. Deterministic labels, marker shapes and/or line patterns retain meaning. Rendering order is fixed by canonical series order, with fixed dimensions/layout, deterministic number formatting and predictable escaping.

Any future public-site integration requires a later separately governed phase. Phase 11 itself changes no Pages/report/publication path.

## Fail-closed validation and Phase 10 replay

The series validator is repository-context-bound and read-only. Given the same repository root plus the immutable commit/tree and pinned Phase 10 validator/config identities in the series record, it must re-enumerate slot candidates and replay the existing Phase 10 comparison builder for every unique-current slot.

For each Phase-10-backed entry, replayed evidence must match the retained comparison status, `comparison_id`, current identity, predecessor identity and relevant metric/source evidence exactly.

For missing or ambiguous slots, immutable candidate re-enumeration must reproduce the recorded cardinality and ambiguity identity list.

The validator fails closed for at least:

- unsupported Phase 11/Phase 10 version, metric key or source identity;
- repository-context or pinned validator/config mismatch;
- invalid/non-hour-aligned/reversed/oversized window;
- unorderable immutable candidate set;
- duplicate, missing or out-of-order hourly slots;
- incomplete/differently ordered ambiguity evidence;
- gap reason outside the frozen vocabulary or contrary to frozen precedence;
- value without replayed `comparison-available` evidence and exact pair provenance;
- numeric value that differs from replayed current-side comparable evidence;
- source status that differs from replayed current-side categorical evidence;
- stripped, merged or reassigned side-specific degraded warnings;
- unsupported derived/aggregate fields;
- continuity claim that violates exact predecessor/current identity equality;
- recomputed `series_id` mismatch.

Malformed series input produces no renderer output.

## Acceptance gates

- [x] A separately authorised Phase 11 delivery-control/implementation-planning issue adopts the frozen #416 design without relaxation.
- [x] A canonical `crypto-temporal-series/v1` builder emits exactly one deterministic record per requested metric/source series and hourly window.
- [x] The builder never uses raw snapshot metrics as a success bypass around Phase 10.
- [x] Window, slot, missing, ambiguity and gap precedence semantics exactly match the frozen contract.
- [x] Numeric and source-status vocabularies are closed and validated fail closed.
- [x] Current and predecessor Phase 10 identity, quality and warning evidence remain separately attributable.
- [x] Series validation replays immutable Phase 10 evidence rather than trusting asserted IDs/values/statuses.
- [x] Numeric continuity is bound to exact predecessor/current identity and never inferred from timestamps alone.
- [x] No interpolation, aggregation, smoothing, normalisation, backfill or inferred values exist.
- [x] The offline renderer produces deterministic semantic HTML, inline SVG and a complete tabular equivalent.
- [x] Source status remains categorical and separate from market movement.
- [x] Accessibility does not depend on colour or visual interpretation alone.
- [x] The closed proof corpus demonstrates all required success/failure/degraded/ambiguity/continuity/tamper cases.
- [x] Two independent runs produce byte-identical canonical series and renderer output.
- [x] Proof requires zero network, provider, model or credential calls.
- [x] Phase 10 semantics, deterministic selector, source snapshots/acquisition, reports/site, workflows, publication, auto-merge and generated `_site/` remain unchanged.

## Delivered implementation slices

Phase 11 was delivered under the accepted four-slice plan in #418 comment `5305066681`:

```text
1. Canonical series builder + validator
   - immutable slot enumeration
   - frozen metric/source/gap vocabulary
   - Phase 10 replay and series identity

2. Deterministic accessible renderer
   - validated series input only
   - static semantic HTML + inline SVG
   - complete tabular equivalent

3. Closed offline proof corpus
   - normal/degraded/missing/ambiguous/failure cases
   - continuity and tamper rejection
   - byte-identical repeatability proof

4. Phase 11 close-out
   - delivery record and concise ledger update
   - delivery-graph N/A disposition under existing compact graph rules
   - roadmap/backlog reconciliation
```

No public-site integration slice belongs to Phase 11.

## Risks and mitigations

### Risk: the series layer bypasses Phase 10 when comparison evidence is unavailable

Mitigation: values require replayed `comparison-available` evidence and exact comparable metric/current source evidence. Raw snapshots may only establish immutable candidate slot membership.

### Risk: chart continuity hides missing or invalid hourly evidence

Mitigation: every requested hour is emitted exactly once; every gap breaks the line; continuity additionally requires exact later-predecessor/earlier-current identity equality.

### Risk: degraded evidence is visually retained but audit attribution is lost

Mitigation: preserve the complete current and predecessor Phase 10 input records independently, including side-specific quality and warning evidence, in canonical series and table output.

### Risk: implementation invents convenient generic gap categories

Mitigation: freeze the complete v1 gap vocabulary and exact precedence/mapping. Unknown Phase 10 states fail closed and require a new reviewed contract version.

### Risk: an asserted comparison hash is treated as trusted provenance

Mitigation: the series validator replays Phase 10 from the immutable commit/tree and requires exact equality with retained comparison identity, pair provenance and relevant evidence.

### Risk: visual presentation becomes implicit market analysis or trading guidance

Mitigation: allow only raw current-side Phase 10 evidence and categorical source status, prohibit derived analytical transformations and keep Phase 11 offline with no public integration authority.

### Risk: Phase 11 expands into acquisition, model or publication work

Mitigation: explicitly exclude providers/models, credentials, acquisition, selectors, reports/site, workflows, publication, auto-merge and generated `_site/` from every implementation slice.

## Definition of done

Phase 11 is complete:

- [x] the roadmap spec and separately authorised parent delivery-control issue exist;
- [x] bounded implementation/proof issues were created only after their own governance gates;
- [x] implementation PRs were merged after exact-head validation and independent review;
- [x] the canonical series and renderer contracts are validated fail closed;
- [x] offline proof records all required gap/degraded/ambiguity/continuity/tamper evidence;
- [x] deterministic repeatability is proved from immutable repository evidence;
- [x] no network/provider/model call or credential is required;
- [x] Phase 10, selector, snapshot/acquisition, report/site/workflow/publication boundaries remain unchanged;
- [x] the Phase 11 delivery record is added under `planning/delivery/`;
- [x] `planning/delivery-log.md` is updated;
- [x] `planning/delivery/delivery.yaml` is explicitly not applicable under the existing compact graph rules;
- [x] `planning/delivery/graph.md` is unchanged because `delivery.yaml` is unchanged;
- [x] roadmap/backlog state is reconciled after close-out;
- [x] generated `_site/` output is not committed.

## Follow-on boundary

A later separately governed phase may decide whether proven Phase 11 visual evidence should integrate with `scripts/build_pages_site.py` or another publication path. Phase 11 does not grant that authority and does not introduce sentiment, forecasting, causality, technical levels, support/resistance, targets, watchlists or trading guidance. No successor phase is selected by this close-out.
