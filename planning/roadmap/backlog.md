# CryptoPulse roadmap backlog

This backlog parks ideas that are useful but outside the currently approved direction. Items here are not commitments. Promote an item into a phase spec only when it has a clear problem statement, acceptance gates, proof path and separate owner authority.

Phase 11 — deterministic temporal visualisation — is the current shaping direction under #416. Phase 10 is complete, the Phase 6 deterministic selector remains the sole active selector, Phase 9 ended `no-stable-material-uplift`, and no model/provider path is currently approved for operational use. Phase 11 remains offline and does not authorise site/publication integration.

## Candidate future phases

### News and event evidence ingestion

Capture credible market event inputs outside any model boundary before asking for narrative. Candidate sources include official exchange announcements, protocol blogs, regulator releases, ETF issuer data, Reuters/Bloomberg-style feeds where licensed, and explicitly labelled secondary news sources.

Why parked: News ingestion needs its own source-quality policy, licensing review, freshness rules and validation contract. A model must not choose or fetch authoritative market facts.

### Previous-hour comparison engine — delivered as Phase 10

Compare consecutive validated snapshots deterministically to identify changes in supported asset, DeFi, stablecoin and source-availability evidence.

Status: complete. Delivered under Phase 10 with the frozen exact-hour, immediate-prior, no-skip/no-fallback contract. See `phase-10-previous-hour-comparison.md` and `../delivery/phase-10-previous-hour-comparison.md`.

### Deterministic charts and visual market cards — promoted to Phase 11 shaping

Generate deterministic temporal visual evidence from the frozen Phase 10 comparison boundary.

Status: the bounded offline portion is promoted into Phase 11 under #416 and `phase-11-deterministic-temporal-visualisation.md`. Phase 11 is limited to canonical `crypto-temporal-series/v1` evidence, deterministic accessible HTML/SVG proof rendering and repeatability validation. Public-site integration, publication paths and broader visual market-card product work remain parked and require separate governance after Phase 11 proof.

### Technical-level calculation policy

Explore whether simple support/resistance or intraday-level annotations can be calculated mechanically and presented as observations rather than trading guidance.

Why parked: Technical levels are close to trading signals. Any future implementation needs strict wording, deterministic calculation rules and compliance review.

### Sentiment and risk taxonomy

Define a controlled vocabulary for conditions such as `risk-on`, `risk-off`, `mixed`, `leverage elevated` or `breadth weakening`, backed by explicit evidence thresholds.

Why parked: Classification should be deterministic first and narrative second. The repository should first establish stable temporal comparison evidence and separately approve any threshold taxonomy.

### LLM safety and moderation pass

Use a separate model or deterministic checker to flag advice-like language, unsupported claims and disclaimer drift in generated prose.

Why parked: No model-authored operational narrative is currently enabled. Revisit only if a separately governed future programme reintroduces model-authored output and demonstrates a concrete moderation gap.

### Automated LLM generation after snapshot merges

Trigger governed LLM analysis automatically after a source snapshot PR merges, rather than requiring `workflow_dispatch`.

Why parked: No model is currently selected or enabled, and automatic generation, scheduling and publication remain disabled. Any future automation requires a new separately governed model programme and completed validation evidence first.

### Expanded approved prose slots in reports

Expand beyond the current deterministic report surfaces into richer approved prose slots across report or site surfaces.

Why parked: Model-authored prose is not currently enabled. Any future expansion should follow separately governed proof that deterministic evidence and validation boundaries are sufficient.

### OpenRouter model bake-off beyond prior proofs

Run a broader evaluation across several OpenRouter models and compare JSON compliance, traceability, tone, hallucination rate, fallback frequency, latency and cost.

Why parked: Phase 9 ended `no-stable-material-uplift` and authorises no further Phase 9 run. Any future model-selection investigation must be a new separately governed programme with new evidence, budget, acceptance gates and execution authority; it is not the current next phase.

### Costed provider/model policy

Evaluate whether a paid model is justified for reliability, structured output quality and lower validation failure rates.

Why parked: No paid-model adoption is currently justified or authorised. Reconsider only after a new model programme has a clear deterministic comparator, product need, acceptance gates and explicit budget authority.

### Human review UX for generated narrative

Improve PR bodies, artefact links or rendered previews so reviewers can inspect evidence bundles, prompts, raw output, validation checks and final prose diffs quickly.

Why parked: There is no active generated-narrative delivery path to optimise. Review UX should follow a separately approved narrative capability rather than create one indirectly.

## Parking lot from the original analyst prompt

These original prompt features should stay parked until deterministic evidence exists and any additional governance requirements are separately approved:

- live or most-recent data collection by a model;
- model-selected credible sources;
- ongoing event summaries from news feeds;
- whale, treasury or exchange-wallet movements;
- ETF flow updates;
- public/site chart integration beyond the bounded offline Phase 11 proof;
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
