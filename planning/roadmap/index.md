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

Phase 13 — deterministic observation-hour comparison and temporal evidence — is the selected shaping/delivery-planning direction under #443/#444. Its accepted design defines a new cadence-slot evidence family over future Phase-12-ready snapshots without reinterpreting frozen Phase 10/11 v1 timing or temporal semantics.

Phase 12 — canonical observation-hour evidence — is complete under #436/#441 and `phase12-observation-hour/v1`. It gives future source snapshots a truthful canonical `run.observation_hour_utc` containing-hour identity while preserving actual `run.generated_at_utc`, source fetch timestamps, historical snapshots and the pinned Phase 10 validator/config identities. Rolling ingestion validates that identity before reviewer evidence or any publication mutation.

Phase 13 is not yet implemented. It must prove exact current/predecessor observation-hour adjacency, fail-closed missing/duplicate/invalid evidence, immutable identity/provenance, deterministic comparison/series records, a bounded 12-metric/8-source temporal vocabulary, and offline repeatability/tamper evidence before it can close.

The deterministic selector delivered in Phase 6 remains the sole active selector. Phase 9 remains closed with `no-stable-material-uplift`.

## Active roadmap direction

| Phase | Status | Planning record | Governing evidence |
| --- | --- | --- | --- |
| Phase 13 — Deterministic observation-hour comparison and temporal evidence | Shaping / delivery planning; not implemented | [phase-13-observation-hour-temporal-evidence.md](phase-13-observation-hour-temporal-evidence.md) | #443 design comments `5305763171`, `5305764744`, `5305765770`; approval `5305767217`; promotion #444 |

Public/site integration of temporal evidence remains parked and is not part of Phase 13.

## Completed roadmap directions

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 4 — Live-site provenance UX | Implementation complete | [phase-04-live-site-provenance-ux.md](phase-04-live-site-provenance-ux.md) | [../delivery/phase-04-live-site-provenance-ux.md](../delivery/phase-04-live-site-provenance-ux.md) |
| Phase 6 — Deterministic claim candidates and bounded model selection | Complete; deterministic selector retained | [phase-06-deterministic-claim-selection.md](phase-06-deterministic-claim-selection.md) | [../delivery/phase-06-deterministic-claim-selection.md](../delivery/phase-06-deterministic-claim-selection.md) |
| Phase 9 — GPT-OSS quality and stability comparison | Complete; `no-stable-material-uplift` | [phase-09-gpt-oss-quality-decision.md](phase-09-gpt-oss-quality-decision.md) | [../delivery/phase-09-gpt-oss-quality-comparison.md](../delivery/phase-09-gpt-oss-quality-comparison.md) |
| Phase 10 — Deterministic previous-hour comparison engine | Complete; exact-hour deterministic comparison evidence | [phase-10-previous-hour-comparison.md](phase-10-previous-hour-comparison.md) | [../delivery/phase-10-previous-hour-comparison.md](../delivery/phase-10-previous-hour-comparison.md) |
| Phase 11 — Deterministic temporal visualisation | Complete; offline deterministic temporal evidence/rendering proof | [phase-11-deterministic-temporal-visualisation.md](phase-11-deterministic-temporal-visualisation.md) | [../delivery/phase-11-deterministic-temporal-visualisation.md](../delivery/phase-11-deterministic-temporal-visualisation.md) |
| Phase 12 — Canonical observation-hour evidence | Complete; future snapshot cadence-bucket identity and enforcement | [phase-12-canonical-observation-hour-evidence.md](phase-12-canonical-observation-hour-evidence.md) | [../delivery/phase-12-canonical-observation-hour-evidence.md](../delivery/phase-12-canonical-observation-hour-evidence.md) |

Phase 10 compares one current repository-owned snapshot with its uniquely resolved immediate predecessor under the frozen exact `3,600`-second, no-skip/no-fallback contract. Phase 11 consumes that evidence offline to produce canonical temporal history and deterministic reviewer-visible rendering. Phase 12 extends the active source-evidence spine with a separate observation-hour identity. Phase 13 is the separately versioned consumer that will use that identity for exact adjacent observation-hour comparison and temporal evidence while leaving Phase 10/11 v1 unchanged.

## Superseded active direction

| Phase | Status | Planning record | Evidence |
| --- | --- | --- | --- |
| Phase 5 — Governed LLM analysis | Research and evaluation complete; full-plan model path superseded by Phase 6 | [phase-05-governed-llm-analysis.md](phase-05-governed-llm-analysis.md) | [Phase 5 evaluation history](../../evaluation/phase-05/README.md) |

Phase 5 implemented the evidence bundle, semantic claim-plan contracts, fail-closed validator, deterministic renderer and protected evaluation machinery. No model was selected and automatic generation was not authorised. Corrective run `29285569716` showed that the remaining full-plan model responsibility was still too broad, so the pending GPT-5.6/Nex calibration was cancelled in favour of deterministic candidate compilation and bounded selection.

The chronology and lessons remain recorded in:

- [`../../evaluation/phase-05/semantic-model-evaluation-retrospective.md`](../../evaluation/phase-05/semantic-model-evaluation-retrospective.md);
- [`../../evaluation/phase-05/corrective-screen-29285569716.md`](../../evaluation/phase-05/corrective-screen-29285569716.md).

## Backlog

Ideas that are useful but not ready for an active phase are parked in:

```text
backlog.md
```

Use the backlog to preserve follow-on ideas without implicitly expanding Phase 13 into public/site integration, model work or another successor capability.

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
