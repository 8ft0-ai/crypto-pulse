# CryptoPulse roadmap backlog

This backlog parks ideas that remain outside the completed Phase 17 trusted-main source-evidence accumulation boundary and the completed Phase 14–16 delivery boundaries. Items here are not commitments. Phase 17 completed under #523 from the approved `trusted-main-source-evidence-accumulation/v1.1` contract; its final Slice E decision enables daily **candidate refresh only**, not candidate/source merge, Phase 14/#477 activation or any other backlog item. Promote another item only when it has a clear problem statement, acceptance gates, proof path and separate owner authority.

Phase 12 — canonical observation-hour evidence — is complete under #436/#441. Future source snapshots carry separately validated containing-hour identity while preserving actual timing evidence, historical snapshots and frozen Phase 10/11 contracts. Phase 13 — deterministic observation-hour comparison and temporal evidence — is complete under #446/#453, providing separately versioned exact adjacent-slot comparison and canonical temporal evidence over Phase-12-ready snapshots. Phase 14 — deterministic site publication — is complete at the safe inert control-plane boundary under #458: the reviewed `deterministic-site-publication/v3` control plane and App/protection boundary are delivered, while the real live stale-base race, live pilot and recurring activation remain deliberately deferred. Phase 15 — public deterministic temporal evidence — is complete under #482 with contract `phase15-public-temporal-evidence/v1`: one repository-bound `BTC.price_usd` 24-slot temporal-evidence page plus one minimum discovery link is delivered and publicly proved through the existing Pages path. Phase 16 is complete under #501 from approved `reader-facing-evidence-experience/v1`, having delivered canonical reader authority + Home/Most recent, temporal reader-state presentation over the unchanged Phase 15 record, and Archive/navigation integration. Phase 17 is complete under #523: deterministic accumulation/recovery, a bounded real source promotion, unchanged consumer/public proof and daily source-candidate refresh were delivered while per-candidate merge remained separately governed. The Phase 6 deterministic selector remains the sole active selector, Phase 9 ended `no-stable-material-uplift`, and no model/provider path is approved for operational use.

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

Why parked: Phase 14 already delivered the safe control plane and left activation absent/`disabled`. V1–V13 demonstrated fail-closed behaviour but did not produce the required real stale-base race observation, and continuing with another timing-only V14+ runner would optimise around scheduler timing rather than prove the production invariant deterministically. There is no current product requirement that justifies operationalising automatic publication now. Completion of Phase 17 does not change or implicitly promote this path.

Any future work must keep `main` as sole publication authority, preserve the existing v3 candidate/attestation/head/base controls and strict required-check protection, remain inert by default until separately authorised execution, and must not revive V1–V13.

### Source-evidence accumulation for temporal usefulness — delivered as Phase 17

The #497 T2 accumulation need is no longer parked. It was separately shaped under #516 as `trusted-main-source-evidence-accumulation/v1.1`, received fresh substantive approval in #516 comment `5425040365`, was selected as **Phase 17 — trusted-main source-evidence accumulation and freshness** by owner decision in comment `5425197783`, and completed under parent delivery-control issue #523.

Delivered scope remained deliberately narrower than automatic publication: exact scheduled-ingestion artifacts and Phase-12-valid snapshot bytes feed a deterministic bounded `H_main + 1 ... H_main + 25` source-only candidate; protected `main` remains the sole public evidence authority; unsafe evidence fails closed unless an exact durable terminal recovery decision excludes it without promotion or synthetic cursor movement; and candidate review/merge remains exact-head and human-governed.

The successful bounded real promotion merged 17 exact canonical source hours through PR #535 and was proved through unchanged Phase 13 / 15 / 16 consumers plus the existing Pages/live-verification path. The separate Slice E decision selected daily candidate refresh, implemented by PR #539 with cron `47 0 * * *` UTC. The schedule may create or refresh a disposable source-only candidate but has no merge capability and no recovery inference authority.

Phase 17 does not activate Phase 14/#477, make a mutable rolling/candidate branch public authority, reinterpret Phase 13/15/16, backfill history, add models/providers/report generation, or make `live/current/up to date` public claims. See `phase-17-trusted-main-source-evidence-accumulation.md` and `../delivery/phase-17-trusted-main-source-evidence-accumulation.md`.

### News and event evidence ingestion

Capture credible market event inputs outside any model boundary before asking for narrative. Candidate sources include official exchange announcements, protocol blogs, regulator releases, ETF issuer data, Reuters/Bloomberg-style feeds where licensed, and explicitly labelled secondary news sources.

Why parked: News ingestion needs its own source-quality policy, licensing review, freshness rules and validation contract. A model must not choose or fetch authoritative market facts.

### Previous-hour comparison engine — delivered as Phase 10

Compare consecutive validated snapshots deterministically to identify changes in supported asset, DeFi, stablecoin and source-availability evidence.

Status: complete. Delivered under Phase 10 with the frozen exact-hour, immediate-prior, no-skip/no-fallback contract. See `phase-10-previous-hour-comparison.md` and `../delivery/phase-10-previous-hour-comparison.md`.

### Observation-hour comparison / temporal consumer — delivered as Phase 13

Use validated `phase12-observation-hour/v1` identity to define an operational cadence-aware comparison/temporal contract for future slot-ready snapshots.

Status: complete. Delivered under Phase 13 as **deterministic observation-hour comparison and temporal evidence**. The accepted implementation provides exact adjacent observation-hour selection, explicit missing/duplicate/invalid evidence, immutable provenance, deterministic repository-bound comparison/series records, bounded 12-metric/8-source temporal vocabulary and closed offline proof while preserving frozen Phase 10/11 v1 semantics.

See `phase-13-observation-hour-temporal-evidence.md` and `../delivery/phase-13-observation-hour-temporal-evidence.md`. Its first bounded public integration is complete separately as Phase 15; Phase 16 changes only the reader projection/presentation of that existing public evidence. Phase 17 increased the trusted source population without changing those evidence identities.

### Deterministic report publication freshness — delivered at the Phase 14 inert boundary

Restore recent public deterministic Markdown reports from already validated source evidence without making a rolling branch a publication authority or adding a model/provider path.

Status: the control-plane portion is complete under #458 as **Phase 14 — deterministic site publication** with contract `deterministic-site-publication/v3`. The delivered direction keeps `main` as the sole publication authority, uses immutable trusted-generation attestation plus exact-head credential-free validation, retains strict stale-base controls and the existing Pages/live-verification path, and leaves publication activation absent/`disabled`.

Not delivered: the real live stale-base race, one live publication pilot, live Pages identity proof for a Phase 14 candidate and recurring activation. Those are not implicit follow-on work; any revisit starts from #477 and requires fresh governance. Phase 17 does not depend on activating this path.

See `phase-14-deterministic-site-publication.md` and `../delivery/phase-14-deterministic-site-publication.md`.

### Public deterministic temporal evidence — delivered as Phase 15

Expose the already-proved Phase 13 observation-hour evidence on the public demo site without reopening frozen Phase 11/12/13 contracts or turning CryptoPulse into a market-product UX.

Status: complete under #482 as **Phase 15 — public deterministic temporal evidence** with contract `phase15-public-temporal-evidence/v1`. The delivered v1 surface is exactly one `metric` / `BTC.price_usd` series over 24 canonical observation-hour slots, one generated `temporal.html` page and one low-prominence homepage discovery link.

The delivered design inherits exact Phase 13 participation and malformed/unorderable-population semantics, uses the maximum canonical participating observation hour as the deterministic anchor, fails closed with no asserted page when participation is empty, preserves duplicate latest-hour ambiguity without fallback, validates the canonical Phase 13 record directly through the narrow Phase 15 renderer boundary, and required separately governed Phase-12-valid evidence on trusted `main` before site integration.

The site integration merged as PR #490 at `99c4ced3001bb227d599173bb5a17011d23eea53`. Existing Pages run `32528437373` automatically deployed that exact state successfully, and the exact deployed artifact was verified under #482 comment `5375652127` for `temporal.html`, commit identity, one homepage discovery link, disclaimer-before-evidence ordering and the complete 24-slot table.

Phase 15 did not activate Phase 14/#477, render from a mutable rolling branch, backfill history, add narrative/forecast/advice, enable a model/provider path, or select broader visual market-card scope. Phase 16 consumes the existing narrow temporal record only for the approved reader-state projection and presentation fixes. Phase 17 added valid source snapshots to protected `main` under separate governance, after which Phase 15 continues to consume them under its frozen semantics.

### Reader-facing evidence experience — delivered as Phase 16

Make Home, Most recent, Temporal evidence and Archive one coherent reader-facing evidence product without weakening exact repository authority, fail-closed semantics, provenance or the AI-demo/non-advice boundary.

Status: complete under #501 as **Phase 16 — reader-facing evidence experience** from approved `reader-facing-evidence-experience/v1`; final exact public proof is recorded against merge `ee46ae895036b60bccfab99e4f462bf5f53c15cd` and Pages run `32633849094`.

Included only:

- canonical report chronology and shared `latest_report` / `current_observation` reader authority;
- Home / `latest.html` reader-first hierarchy and safe repository-recency wording;
- temporal reader-state projection/presentation over the unchanged Phase 15 `BTC.price_usd` 24-slot evidence;
- Archive canonical chronology, actual coverage/discontinuity semantics, bounded taxonomy/filtering and navigation integration.

Phase 16 explicitly excluded #497 T2 evidence accumulation/promotion, Phase 14/#477 operationalisation, additional temporal series, new providers/models, derived analytics, forecasts, recommendations or trading signals. The T2 accumulation path was subsequently delivered as Phase 17; all other exclusions remain parked.

See `phase-16-reader-facing-evidence-experience.md` for the delivered reader-facing planning contract.

### Deterministic charts and visual market cards — broader product scope still parked beyond Phase 17

Generate deterministic visual evidence and market-card product surfaces beyond the exact point-in-time fields and single Phase 15 BTC temporal series already authorised for public presentation.

Status: the bounded offline rendering foundation is complete under Phase 11. `crypto-temporal-series/v1`, repository-bound replay validation, deterministic accessible HTML/SVG rendering and the closed repeatability proof corpus are delivered and recorded in `../delivery/phase-11-deterministic-temporal-visualisation.md`.

Operational evidence prerequisites are also complete: Phase 12 provides future slot-ready observation-hour identity, Phase 13 provides the separately versioned observation-hour comparison/temporal consumer, Phase 15 proved one narrow public `BTC.price_usd` integration, Phase 16 made that existing evidence reader-first without broadening its authority, and Phase 17 accumulated more trusted source evidence into those frozen consumers.

Still parked beyond Phase 17: additional metrics or source-status series, derived/aggregate temporal metrics, richer analytical market cards not directly authorised by the exact current observation, and any trend/interpretive analytics. Those require separate product/evidence/governance decisions rather than being implied by a fuller trusted evidence population.

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

Why parked: No model is currently selected or enabled. Phase 14 delivered only a deterministic publication control plane, Phase 15 delivered only deterministic historical temporal evidence, Phase 16 delivered only a reader-facing evidence/presentation layer, and Phase 17 delivered source-evidence accumulation only; none authorises model generation, model scheduling or model credentials. Any future LLM automation requires a new separately governed model programme and completed validation evidence first.

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

These original prompt features remain parked after completion of the Phase 10–17 evidence/control-plane/reader/accumulation foundations. Each requires separate product, evidence and governance decisions before implementation:

- live or most-recent data collection by a model;
- model-selected credible sources;
- ongoing event summaries from news feeds;
- whale, treasury or exchange-wallet movements;
- ETF flow updates;
- public/site chart integration beyond the single completed Phase 15 `BTC.price_usd` 24-slot proof and its Phase 16 reader presentation;
- support and resistance levels;
- trader watchlists;
- causal claims about why price moved;
- broad sentiment calls not tied to defined evidence thresholds.

## Promotion criteria

Before another backlog item becomes an active phase or implementation issue, define:

- [ ] source of truth and data ownership;
- [ ] validation rules;
- [ ] public-facing demo and non-advice boundaries;
- [ ] fallback behaviour;
- [ ] proof artefacts;
- [ ] acceptance gates;
- [ ] whether site generation, raw reports, workflows or planning records are affected;
- [ ] separate owner authority for promotion and delivery.
