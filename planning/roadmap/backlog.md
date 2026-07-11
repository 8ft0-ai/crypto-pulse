# CryptoPulse roadmap backlog

This backlog parks ideas that are useful but out of scope for the active phase. Items here are not commitments. Promote an item into a phase spec only when it has a clear problem statement, acceptance gates, and proof path.

## Candidate future phases

### News and event evidence ingestion

Capture credible market event inputs outside the LLM before asking for narrative. Candidate sources include official exchange announcements, protocol blogs, regulator releases, ETF issuer data, Reuters/Bloomberg-style feeds where licensed, and explicitly labelled secondary news sources.

Why parked: Phase 5 should not let the model choose or fetch market facts. News ingestion needs its own source-quality policy, licensing review, freshness rules, and validation contract.

### Previous-hour comparison engine

Compare consecutive validated snapshots deterministically to identify changes in asset direction, volume, dominance, liquidations, and source availability.

Why parked: This is high-value for hourly reports, but it should be computed before the LLM sees evidence. Phase 5 can summarise current evidence without needing a new comparison layer.

### Deterministic charts and visual market cards

Generate charts from archived snapshot data, such as BTC/ETH price movement, market-cap movement, top asset 1h moves, dominance, and liquidations where available.

Why parked: Charts should be deterministic site/rendering work, not model-generated. This likely needs data-series storage and accessible visual design.

### Technical-level calculation policy

Explore whether simple support/resistance or intraday-level annotations can be calculated mechanically and presented as observations rather than trading guidance.

Why parked: Technical levels are close to trading signals. Any future implementation needs strict wording, deterministic calculation rules, and compliance review.

### Sentiment and risk taxonomy

Define a controlled vocabulary for conditions such as `risk-on`, `risk-off`, `mixed`, `leverage elevated`, or `breadth weakening`, backed by explicit evidence thresholds.

Why parked: LLM-written sentiment can easily overreach. If added, the classification should be deterministic first and narrative second.

### LLM safety and moderation pass

Use a separate model or deterministic checker to flag advice-like language, unsupported claims, and disclaimer drift in generated prose.

Why parked: Phase 5 should begin with deterministic validators over structured analysis JSON. A model-based safety pass may become useful after the first proof loop shows which failures are common.

### Automated LLM generation after snapshot merges

Trigger governed LLM analysis automatically after a source snapshot PR merges, rather than requiring `workflow_dispatch`.

Why parked: Phase 5 should prove manual generation first. Automation should wait until validation, cost controls, and evaluation evidence are strong enough to justify unattended runs.

### Expanded approved prose slots in reports

Expand beyond the initial deterministically rendered structured-analysis report into richer approved prose slots across report or site surfaces.

Why parked: Start with constrained structured JSON and deterministic rendering so reviewers can evaluate model behaviour before broader prose becomes part of the product experience.

### OpenRouter model bake-off beyond initial proof

Run a broader evaluation across several free and paid OpenRouter models and compare JSON compliance, traceability, tone, hallucination rate, fallback frequency, latency, and cost.

Why parked: Phase 5 should include a small historical evaluation corpus for the initial pinned model choice. A broader bake-off is useful later, especially before paid model adoption or automatic scheduling.

### Costed provider/model policy

Evaluate whether a paid model is justified for reliability, structured output quality, and lower validation failure rates.

Why parked: The next phase should prove value with free OpenRouter models first. Paid dependencies require explicit approval.

### Human review UX for generated narrative

Improve PR bodies, artefact links, or rendered previews so reviewers can inspect evidence bundle, prompt, raw output, validation checks, and final prose diff quickly.

Why parked: Phase 5 can use simple artefacts first. Review UX can be improved once the artefact shape stabilises.

## Parking lot from the original analyst prompt

These original prompt features should stay parked until deterministic evidence exists:

- live or most-recent data collection by the model;
- model-selected credible sources;
- ongoing event summaries from news feeds;
- whale, treasury, or exchange-wallet movements;
- ETF flow updates;
- chart generation;
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
- [ ] whether site generation, raw reports, workflows, or planning records are affected.
