# CryptoPulse roadmap backlog

This backlog parks ideas that are useful but outside the completed Phase 14 safe inert-boundary delivery and the selected Phase 15 public deterministic temporal-evidence direction. Items here are not commitments. Promote an item into a phase spec only when it has a clear problem statement, acceptance gates, proof path and separate owner authority.

Phase 12 — canonical observation-hour evidence — is complete under #436/#441. Future source snapshots carry separately validated containing-hour identity while preserving actual timing evidence, historical snapshots and frozen Phase 10/11 contracts. Phase 13 — deterministic observation-hour comparison and temporal evidence — is complete under #446/#453, providing separately versioned exact adjacent-slot comparison and canonical temporal evidence over Phase-12-ready snapshots. Phase 14 — deterministic site publication — is complete at the safe inert control-plane boundary under #458: the reviewed `deterministic-site-publication/v3` control plane and App/protection boundary are delivered, while the real live stale-base race, live pilot and recurring activation remain deliberately deferred. Phase 15 — public deterministic temporal evidence — is selected under #479/#480 only for the bounded public integration of one validated `BTC.price_usd` 24-slot Phase 13 series. The Phase 6 deterministic selector remains the sole active selector, Phase 9 ended `no-stable-material-uplift`, and no model/provider path is approved for operational use.

## Candidate future phases

### Deterministic publication operationalisation and live stale-base proof

If automatic deterministic publication later becomes valuable enough to operate, resume from #477 rather than reopening the consumed Phase 14 timing-runner series.

Candidate sequence:

```text
#477 deterministic inert live-proof carrier
  -> real stale-base refusal proof
  -> separately authorised bounded live pilot
  -> existing Pages/live identity adjudication
  -> separately authorised recurring-activation decision
```

Why parked: Phase 14 already delivered the safe control plane and left activation absent/`disabled`. V1–V13 demonstrated fail-closed behaviour but did not produce the required real stale-base race observation, and continuing with another timing-only V14+ runner would optimise around scheduler timing rather than prove the production invariant deterministically. There is no current product requirement that justifies operationalising automatic publication now.

Any future work must keep `main` as sole publication authority, preserve the existing v3 candidate/attestation/head/base controls and strict required-check protection, remain inert by default until separately authorised execution, and must not revive V1–V13.

### News and event evidence ingestion

Capture credible market event inputs outside any model boundary before asking for narrative. Candidate sources include official exchange announcements, protocol blogs, regulator releases, ETF issuer data, Reuters/Bloomberg-style feeds where licensed, and explicitly labelled secondary news sources.

Why parked: News ingestion needs its own source-quality policy, licensing review, freshness rules and validation contract. A model must not choose or fetch authoritative market facts.

### Previous-hour comparison engine — delivered as Phase 10

Compare consecutive validated snapshots deterministically to identify changes in supported asset, DeFi, stablecoin and source-availability evidence.

Status: complete. Delivered under Phase 10 with the frozen exact-hour, immediate-prior, no-skip/no-fallback contract. See `phase-10-previous-hour-comparison.md` and `../delivery/phase-10-previous-hour-comparison.md`.

### Observation-hour comparison / temporal consumer — delivered as Phase 13

Use validated `phase12-observation-hour/v1` identity to define an operational cadence-aware comparison/temporal contract for future slot-ready snapshots.

Status: complete. Delivered under Phase 13 as **deterministic observation-hour comparison and temporal evidence**. The accepted implementation provides exact adjacent observation-hour selection, explicit missing/duplicate/invalid evidence, immutable provenance, deterministic repository-bound comparison/series records, bounded 12-metric/8-source temporal vocabulary and closed offline proof while preserving frozen Phase 10/11 v1 semantics.

See `phase-13-observation-hour-temporal-evidence.md` and `../delivery/phase-13-observation-hour-temporal-evidence.md`. The bounded public integration of that evidence is now selected separately as Phase 15; broader temporal product expansion remains parked below.

### Deterministic report publication freshness — delivered at the Phase 14 inert boundary

Restore recent public deterministic Markdown reports from already validated source evidence without making a rolling branch a publication authority or adding a model/provider path.

Status: the control-plane portion is complete under #458 as **Phase 14 — deterministic site publication** with contract `deterministic-site-publication/v3`. The delivered direction keeps `main` as the sole publication authority, uses immutable trusted-generation attestation plus exact-head credential-free validation, retains strict stale-base controls and the existing Pages/live-verification path, and leaves publication activation absent/`disabled`.

Not delivered: the real live stale-base race, one live publication pilot, live Pages identity proof for a Phase 14 candidate and recurring activation. Those are not implicit follow-on work; any revisit starts from #477 and requires fresh governance.

See `phase-14-deterministic-site-publication.md` and `../delivery/phase-14-deterministic-site-publication.md`.

### Public deterministic temporal evidence — promoted as Phase 15

Expose the already-proved Phase 13 observation-hour evidence on the public demo site without reopening frozen Phase 11/12/13 contracts or turning CryptoPulse into a market-product UX.

Status: promoted under #479/#480 as **Phase 15 — public deterministic temporal evidence** with contract `phase15-public-temporal-evidence/v1`. The selected v1 surface is exactly one `metric` / `BTC.price_usd` series over 24 canonical observation-hour slots, one generated `temporal.html` page and one low-prominence homepage discovery link.

The selected design inherits exact Phase 13 participation and malformed/unorderable-population semantics, uses the maximum canonical participating observation hour as the deterministic anchor, fails closed with no asserted page when participation is empty, preserves duplicate latest-hour ambiguity without fallback, validates the canonical Phase 13 record directly through a new narrow renderer boundary, and requires separately governed Phase-12-valid evidence on trusted `main` before site integration.

This promotion does not activate Phase 14/#477, promote source evidence implicitly, render from a mutable rolling branch, backfill history, add narrative/forecast/advice, enable a model/provider path, or select broader visual market-card scope.

### Deterministic charts and visual market cards — broader product scope still parked

Generate additional deterministic temporal visual evidence and market-card product surfaces beyond the single Phase 15 BTC price proof.

Status: the bounded offline rendering foundation is complete under Phase 11. `crypto-temporal-series/v1`, repository-bound replay validation, deterministic accessible HTML/SVG rendering and the closed repeatability proof corpus are delivered and recorded in `../delivery/phase-11-deterministic-temporal-visualisation.md`.

Operational evidence prerequisites are also complete: Phase 12 provides future slot-ready observation-hour identity and Phase 13 provides the separately versioned observation-hour comparison/temporal consumer. Phase 15 now selects only the narrow public `BTC.price_usd` proof.

Still parked: additional metrics or source-status series, richer market-card UX, broader navigation/product treatment and any derived analytics. Those require separate product/evidence/governance decisions after Phase 15 rather than being implied by it.

### Technical-level calculation policy

Explore whether simple support/resistance or intraday-level annotations can be calculated mechanically and presented as observations rather than trading guidance.

Why parked: Technical levels are close to trading signals. Any future implementation needs strict wording, deterministic calculation rules and compliance review.

### Sentiment and risk taxonomy

Define a controlled vocabulary for conditions such as `risk-on`, `risk-off`, `mixed`, `leverage elevated` or `breadth weakening`, backed by explicit evidence thresholds.

Why parked: Classification should be deterministic first and narrative second. The repository has deterministic comparison/temporal evidence foundations, but any threshold taxonomy still requires separate shaping and governance.

### LLM safety and moderation pass

Use a separate model or deterministic checker to flag advice-like language, unsupported claims and disclaimer drift in generated prose.

Why parked: No model-authored operational narrative is currently enabled. Revisit only if a separately governed future programme reintroduces model-authored output and demonstrates a concrete moderation gap.

### Automated LLM generation after snapshot merges

Trigger governed LLM analysis automatically after a source snapshot PR merges, rather than requiring `workflow_dispatch`.

Why parked: No model is currently selected or enabled. Phase 14 delivered only a deterministic publication control plane and Phase 15 adds only deterministic historical temporal evidence; neither authorises model generation, model scheduling or model credentials. Any future LLM automation requires a new separately governed model programme and completed validation evidence first.

### Expanded approved prose slots in reports

Expand beyond the current deterministic report surfaces into richer approved prose slots across report or site surfaces.

Why parked: Model-authored prose is not currently enabled. Any future expansion should follow separately governed proof that deterministic evidence and validation boundaries are sufficient.

### OpenRouter model bake-off beyond prior proofs

Run a broader evaluation across several OpenRouter models and compare JSON compliance, traceability, tone, hallucination rate, fallback frequency, latency and cost.

Why parked: Phase 9 ended `no-stable-material-uplift` and authorises no further Phase 9 run. Any future model-selection investigation must be a new separately governed programme with new evidence, budget, acceptance gates and execution authority; it is not an automatically selected successor.

### Costed provider/model policy

Evaluate whether a paid model is justified for reliability, structured output quality and lower validation failure rates.

Why parked: No paid-model adoption is currently justified or authorised. Reconsider only after a new model programme has a clear deterministic comparator, product need, acceptance gates and explicit budget authority.

### Human review UX for generated narrative

Improve PR bodies, artefact links or rendered previews so reviewers can inspect evidence bundles, prompts, raw output, validation checks and final prose diffs quickly.

Why parked: There is no active generated-narrative delivery path to optimise. Review UX should follow a separately approved narrative capability rather than create one indirectly.

## Parking lot from the original analyst prompt

These original prompt features remain parked after completion of the Phase 10–14 evidence/control-plane foundations and selection of the narrow Phase 15 public temporal-evidence proof. Each requires separate product, evidence and governance decisions before implementation:

- live or most-recent data collection by a model;
- model-selected credible sources;
- ongoing event summaries from news feeds;
- whale, treasury or exchange-wallet movements;
- ETF flow updates;
- public/site chart integration beyond the single Phase 15 `BTC.price_usd` 24-slot proof;
- support and resistance levels;
- trader watchlists;
- causal claims about why price moved;
- broad sentiment calls not tied to defined evidence thresholds.

## Promotion criteria

Before a backlog item becomes an active phase or implementation issue, define:

- [ ] source of truth and data ownership;
- [ ] validation rules;
- [ ] public-facing demo and non-advice boundaries;
- [ ] fallback behaviour;
- [ ] proof artefacts;
- [ ] acceptance gates;
- [ ] whether site generation, raw reports, workflows or planning records are affected;
- [ ] separate owner authority for promotion and delivery.
