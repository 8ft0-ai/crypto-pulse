# CryptoPulse roadmap backlog

This backlog parks ideas that are useful but outside completed Phase 13 and the selected Phase 14 deterministic-publication direction. Items here are not commitments. Promote an item into a phase spec only when it has a clear problem statement, acceptance gates, proof path and separate owner authority.

Phase 12 — canonical observation-hour evidence — is complete under #436/#441. Future source snapshots carry separately validated containing-hour identity while preserving actual timing evidence, historical snapshots and frozen Phase 10/11 contracts. Phase 13 — deterministic observation-hour comparison and temporal evidence — is complete under #446/#453, providing separately versioned exact adjacent-slot comparison and canonical temporal evidence over Phase-12-ready snapshots. Phase 14 — deterministic site publication — is now selected under #455/#456 only to restore recent deterministic report freshness through the accepted `deterministic-site-publication/v3` boundary. The Phase 6 deterministic selector remains the sole active selector, Phase 9 ended `no-stable-material-uplift`, and no model/provider path is approved for operational use.

## Candidate future phases

### News and event evidence ingestion

Capture credible market event inputs outside any model boundary before asking for narrative. Candidate sources include official exchange announcements, protocol blogs, regulator releases, ETF issuer data, Reuters/Bloomberg-style feeds where licensed, and explicitly labelled secondary news sources.

Why parked: News ingestion needs its own source-quality policy, licensing review, freshness rules and validation contract. A model must not choose or fetch authoritative market facts.

### Previous-hour comparison engine — delivered as Phase 10

Compare consecutive validated snapshots deterministically to identify changes in supported asset, DeFi, stablecoin and source-availability evidence.

Status: complete. Delivered under Phase 10 with the frozen exact-hour, immediate-prior, no-skip/no-fallback contract. See `phase-10-previous-hour-comparison.md` and `../delivery/phase-10-previous-hour-comparison.md`.

### Observation-hour comparison / temporal consumer — delivered as Phase 13

Use validated `phase12-observation-hour/v1` identity to define an operational cadence-aware comparison/temporal contract for future slot-ready snapshots.

Status: complete. Delivered under Phase 13 as **deterministic observation-hour comparison and temporal evidence**. The accepted implementation provides exact adjacent observation-hour selection, explicit missing/duplicate/invalid evidence, immutable provenance, deterministic repository-bound comparison/series records, bounded 12-metric/8-source temporal vocabulary and closed offline proof while preserving frozen Phase 10/11 v1 semantics.

See `phase-13-observation-hour-temporal-evidence.md` and `../delivery/phase-13-observation-hour-temporal-evidence.md`. Public/site integration of that temporal evidence remains outside Phase 13 and separately parked below.

### Deterministic report publication freshness — promoted as Phase 14

Restore recent public deterministic Markdown reports from already validated source evidence without making a rolling branch a publication authority or adding a model/provider path.

Status: promoted under #455/#456 as **Phase 14 — deterministic site publication** with contract `deterministic-site-publication/v3`. The selected direction keeps `main` as the sole publication authority, uses immutable trusted-generation attestation plus exact-head credential-free validation, requires strict stale-base refusal, retains the existing Pages/live-verification path, and remains inert until separately authorised provisioning/pilot/recurring gates. See `phase-14-deterministic-site-publication.md`.

This promotion does not select Phase 11/13 temporal rendering for public use and does not authorise App provisioning or production activation.

### Deterministic charts and visual market cards — offline foundation delivered in Phase 11

Generate deterministic temporal visual evidence from the frozen Phase 10 comparison boundary.

Status: the bounded offline rendering foundation is complete under Phase 11. `crypto-temporal-series/v1`, repository-bound replay validation, deterministic accessible HTML/SVG rendering and the closed repeatability proof corpus are delivered and recorded in `../delivery/phase-11-deterministic-temporal-visualisation.md`.

Operational evidence prerequisites are also complete: Phase 12 provides future slot-ready observation-hour identity and Phase 13 provides the separately versioned observation-hour comparison/temporal consumer.

Still parked: public-site integration of temporal evidence and broader visual market-card product work. Phase 14 selects only deterministic Markdown report publication freshness; it does not select public use of the Phase 11 renderer or Phase 13 series.

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

Why parked: No model is currently selected or enabled. Phase 14 concerns deterministic report publication only and does not authorise model generation, model scheduling or model credentials. Any future LLM automation requires a new separately governed model programme and completed validation evidence first.

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

These original prompt features remain parked after completion of the Phase 10–13 evidence foundations and selection of the narrow Phase 14 deterministic-publication path. Each requires separate product, evidence and governance decisions before implementation:

- live or most-recent data collection by a model;
- model-selected credible sources;
- ongoing event summaries from news feeds;
- whale, treasury or exchange-wallet movements;
- ETF flow updates;
- public/site chart integration beyond the delivered offline Phase 11 renderer and Phase 13 observation-hour evidence consumer;
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
