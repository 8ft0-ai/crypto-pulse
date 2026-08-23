# CryptoPulse roadmap

This directory contains active, future, and retrospective forward-looking planning records for CryptoPulse delivery phases.

Roadmap documents explain intended work before delivery. Completed proof and close-out evidence belongs in `planning/delivery/`, with `planning/delivery-log.md` retained as the concise chronological ledger.

## Planning versus delivery

```text
planning/roadmap/  -> active, future, or reconstructed forward-looking phase specs
planning/delivery/ -> completed phase close-out records
planning/delivery-log.md -> concise chronological ledger
docs/              -> repository, product, and engineering docs
```

## Phase-pack operating model

Future phases should use a small phase pack:

```text
phase spec in planning/roadmap/       -> intent, scope, risks, and definition of done
parent phase issue                    -> delivery control and linked-work checklist
linked child issues                   -> executable work breakdown
pull requests                         -> implementation and validation evidence
close-out comments                    -> final proof trail
completed record in planning/delivery/ -> post-delivery close-out artefact
```

Native GitHub sub-issues are optional. The connector can create and update issues, but cannot reliably create native sub-issue relationships, so parent/child structure should be explicit in Markdown and issue bodies.

## Future phase template

Use the template when shaping a new phase:

```text
phase-template.md
```

A new roadmap phase spec should stay forward-looking. At close-out, put completed evidence into `planning/delivery/` and keep the roadmap directory focused on planning intent.

## Current roadmap position

Phase 16 — reader-facing evidence experience — is complete under #501 and `reader-facing-evidence-experience/v1`. Its three reviewed combined slices delivered canonical reader authority plus Home / Most recent, temporal reader-state projection over the unchanged Phase 15 record, and Archive reader model plus navigation integration. The exact final merge `ee46ae895036b60bccfab99e4f462bf5f53c15cd` was built and deployed by Pages run `32633849094`, and the required live Home, latest, Archive and temporal surfaces matched the deployed artifact byte-for-byte.

Phase 16 keeps canonical report chronology, `latest_report`, `current_observation` and the existing Phase 15 temporal series as distinct authorities; preserves fail-closed newest-observation semantics and exact source-snapshot relation; uses safe repository-recency language rather than claiming live/current freshness; retains the public AI-demo/non-advice boundary and exact provenance; and explicitly excludes #497 T2 source-evidence accumulation/promotion, Phase 14 activation and #477.

Phase 15 — public deterministic temporal evidence — is complete under #482 and `phase15-public-temporal-evidence/v1`. It exposes exactly one validated Phase 13 `metric` / `BTC.price_usd` series over 24 canonical observation-hour slots through one generated temporal page plus one low-prominence homepage discovery link, using the exact checked-out repository commit as public evidence authority. The exact merged site state `99c4ced3001bb227d599173bb5a17011d23eea53` was automatically deployed by Pages run `32528437373`, and the exact deployed artifact was verified under #482 comment `5375652127`.

Phase 14 — deterministic site publication — remains complete at the safe inert control-plane boundary under #458 and `deterministic-site-publication/v3`. The reviewed control plane, publication-App/protection boundary, non-merging App integration proof and candidate attestation/head-change controls are delivered, but the real live stale-base race, live publication pilot and recurring activation were deliberately deferred rather than represented as complete.

The deferred deterministic live stale-base proof/operationalisation path remains parked in #477. It is backlog work and is not part of Phase 16. Publication activation remains absent/`disabled`, normal ingestion cadence is hourly `17 * * * *`, and no automatic deterministic publication rollout is active.

Phase 13 — deterministic observation-hour comparison and temporal evidence — remains complete under #446/#453. It delivers the separately versioned `phase13-observation-hour-adjacency/v1`, `crypto-observation-hour-comparison/v1` and `crypto-observation-hour-series/v1` evidence family over Phase-12-ready snapshots without reinterpreting frozen Phase 10/11 v1 timing or temporal semantics.

Phase 12 — canonical observation-hour evidence — remains complete under #436/#441 and `phase12-observation-hour/v1`. It gives future source snapshots a truthful canonical `run.observation_hour_utc` containing-hour identity while preserving actual `run.generated_at_utc`, source fetch timestamps, historical snapshots and the pinned Phase 10 validator/config identities. Rolling ingestion validates that identity before reviewer evidence or any publication mutation.

Phase 13 proves exact current/predecessor observation-hour adjacency, fail-closed missing/duplicate/invalid evidence, immutable identity/provenance, deterministic comparison/series records, the bounded 12-metric/8-source temporal vocabulary, and offline repeatability/tamper evidence. Phase 15 consumed that evidence under separate governance and preserved the frozen semantics exactly. Phase 16 changes reader projection and information hierarchy without widening those evidence contracts.

The deterministic selector delivered in Phase 6 remains the sole active selector. Phase 9 remains closed with `no-stable-material-uplift`.

## Active roadmap direction

No active successor phase is selected.

Phase 16 is complete. Any next phase must return through normal shaping, fresh substantive review and separate owner promotion/delivery authority. #497 T2 evidence accumulation, Phase 14/#477 operationalisation, broader temporal analytics, model/provider work and trading-oriented features remain parked rather than inheriting Phase 16 authority.

## Completed roadmap directions

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 4 — Live-site provenance UX | Implementation complete | [phase-04-live-site-provenance-ux.md](phase-04-live-site-provenance-ux.md) | [../delivery/phase-04-live-site-provenance-ux.md](../delivery/phase-04-live-site-provenance-ux.md) |
| Phase 6 — Deterministic claim candidates and bounded model selection | Complete; deterministic selector retained | [phase-06-deterministic-claim-selection.md](phase-06-deterministic-claim-selection.md) | [../delivery/phase-06-deterministic-claim-selection.md](../delivery/phase-06-deterministic-claim-selection.md) |
| Phase 9 — GPT-OSS quality and stability comparison | Complete; `no-stable-material-uplift` | [phase-09-gpt-oss-quality-decision.md](phase-09-gpt-oss-quality-decision.md) | [../delivery/phase-09-gpt-oss-quality-comparison.md](../delivery/phase-09-gpt-oss-quality-comparison.md) |
| Phase 10 — Deterministic previous-hour comparison engine | Complete; exact-hour deterministic comparison evidence | [phase-10-previous-hour-comparison.md](phase-10-previous-hour-comparison.md) | [../delivery/phase-10-previous-hour-comparison.md](../delivery/phase-10-previous-hour-comparison.md) |
| Phase 11 — Deterministic temporal visualisation | Complete; offline deterministic temporal evidence/rendering proof | [phase-11-deterministic-temporal-visualisation.md](phase-11-deterministic-temporal-visualisation.md) | [../delivery/phase-11-deterministic-temporal-visualisation.md](../delivery/phase-11-deterministic-temporal-visualisation.md) |
| Phase 12 — Canonical observation-hour evidence | Complete; future snapshot cadence-bucket identity and enforcement | [phase-12-canonical-observation-hour-evidence.md](phase-12-canonical-observation-hour-evidence.md) | [../delivery/phase-12-canonical-observation-hour-evidence.md](../delivery/phase-12-canonical-observation-hour-evidence.md) |
| Phase 13 — Deterministic observation-hour comparison and temporal evidence | Complete; adjacent-slot comparison and canonical temporal evidence proved offline | [phase-13-observation-hour-temporal-evidence.md](phase-13-observation-hour-temporal-evidence.md) | [../delivery/phase-13-observation-hour-temporal-evidence.md](../delivery/phase-13-observation-hour-temporal-evidence.md) |
| Phase 14 — Deterministic site publication | Complete at safe inert control-plane boundary; operational activation deferred | [phase-14-deterministic-site-publication.md](phase-14-deterministic-site-publication.md) | [../delivery/phase-14-deterministic-site-publication.md](../delivery/phase-14-deterministic-site-publication.md) |
| Phase 15 — Public deterministic temporal evidence | Complete; bounded repository-bound BTC temporal evidence published through the existing site pipeline | [phase-15-public-deterministic-temporal-evidence.md](phase-15-public-deterministic-temporal-evidence.md) | [../delivery/phase-15-public-deterministic-temporal-evidence.md](../delivery/phase-15-public-deterministic-temporal-evidence.md) |
| Phase 16 — Reader-facing evidence experience | Complete; coherent reader-facing evidence surfaces with authority separation and exact public proof | [phase-16-reader-facing-evidence-experience.md](phase-16-reader-facing-evidence-experience.md) | [../delivery/phase-16-reader-facing-evidence-experience.md](../delivery/phase-16-reader-facing-evidence-experience.md) |

Phase 10 compares one current repository-owned snapshot with its uniquely resolved immediate predecessor under the frozen exact `3,600`-second, no-skip/no-fallback contract. Phase 11 consumes that evidence offline to produce canonical temporal history and deterministic reviewer-visible rendering. Phase 12 extends the active source-evidence spine with a separate observation-hour identity. Phase 13 consumes that identity under its separately versioned exact adjacent-slot comparison/series contracts while leaving Phase 10/11 v1 unchanged. Phase 14 adds a reviewed inert deterministic publication control plane and trusted App/protection boundary but deliberately stops before live operational publication. Phase 15 separately exposes one narrow Phase 13 temporal-evidence consumer on the existing public site. Phase 16 is the separately governed reader-facing successor over those existing evidence foundations.

## Superseded active direction

| Phase | Status | Planning record | Evidence |
| --- | --- | --- | --- |
| Phase 5 — Governed LLM analysis | Research and evaluation complete; full-plan model path superseded by Phase 6 | [phase-05-governed-llm-analysis.md](phase-05-governed-llm-analysis.md) | [Phase 5 evaluation history](../../evaluation/phase-05/README.md) |

Phase 5 implemented the evidence bundle, semantic claim-plan contracts, fail-closed validator, deterministic renderer and protected evaluation machinery. No model was selected and automatic generation was not authorised. Corrective run `29285569716` showed that the remaining full-plan model responsibility was still too broad, so the pending GPT-5.6/Nex calibration was cancelled in favour of deterministic candidate compilation and bounded selection.

The chronology and lessons remain recorded in:

- [`../../evaluation/phase-05/semantic-model-evaluation-retrospective.md`](../../evaluation/phase-05/semantic-model-evaluation-retrospective.md);
- [`../../evaluation/phase-05/corrective-screen-29285569716.md`](../../evaluation/phase-05/corrective-screen-29285569716.md).

## Backlog

Ideas that are useful but outside the selected Phase 16 direction remain parked in:

```text
backlog.md
```

Use the backlog to preserve follow-on ideas without turning Phase 16 into implicit authority for #497 T2 evidence accumulation, deferred Phase 14 operationalisation, additional temporal series/derived analytics, model work or another capability.

## Retrospective roadmap specs

Phases 1–3 were reconstructed after delivery to preserve the intended roadmap shape alongside the completed delivery records.

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 1 — Source evidence spine | Delivered; retrospective roadmap spec | [phase-01-source-evidence-spine.md](phase-01-source-evidence-spine.md) | [../delivery/phase-01-source-evidence-spine.md](../delivery/phase-01-source-evidence-spine.md) |
| Phase 2 — Deterministic report review loop | Delivered; retrospective roadmap spec | [phase-02-deterministic-report-review-loop.md](phase-02-deterministic-report-review-loop.md) | [../delivery/phase-02-deterministic-report-review-loop.md](../delivery/phase-02-deterministic-report-review-loop.md) |
| Phase 3 — Self-proving generated report PRs | Delivered; retrospective roadmap spec | [phase-03-self-proving-generated-report-prs.md](phase-03-self-proving-generated-report-prs.md) | [../delivery/phase-03-self-proving-generated-report-prs.md](../delivery/phase-03-self-proving-generated-report-prs.md) |

## Delivery records

For completed phase records, see:

```text
../delivery/index.md
```

For the concise chronological ledger, see:

```text
../delivery-log.md
```
