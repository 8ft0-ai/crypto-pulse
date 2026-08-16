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

Phase 12 — canonical observation-hour evidence — is the sole active shaping direction after #431 accepted `phase12-observation-hour/v1` in comment `5305450450` and separately authorised roadmap promotion in comment `5305450958`.

Phase 12 addresses an operational prerequisite discovered after Phase 11: real source snapshots preserve actual runtime `run.generated_at_utc`, while the frozen Phase 10/11 v1 contracts use strict actual-time and exact-hour semantics. Phase 12 may add a truthful future-snapshot `run.observation_hour_utc` containing-hour identity while preserving actual generation/fetch timestamps, historical snapshots and the pinned Phase 10 validator/config identities.

Phase 12 does **not** make Phase 10/11 v1 a live hourly temporal pipeline. Any future comparison or temporal consumer that uses observation-hour identity requires a new separately reviewed versioned contract. Public/site integration of the proven Phase 11 renderer therefore remains parked.

The deterministic selector delivered in Phase 6 remains the sole active selector. Phase 9 remains closed with `no-stable-material-uplift`, Phase 10 remains the frozen deterministic previous-hour comparison boundary, and Phase 11 remains the completed offline temporal evidence/rendering capability.

## Active roadmap direction

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 12 — Canonical observation-hour evidence | Shaping; design accepted under #431; implementation separately gated | [phase-12-canonical-observation-hour-evidence.md](phase-12-canonical-observation-hour-evidence.md) | Pending |

## Completed roadmap directions

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 4 — Live-site provenance UX | Implementation complete | [phase-04-live-site-provenance-ux.md](phase-04-live-site-provenance-ux.md) | [../delivery/phase-04-live-site-provenance-ux.md](../delivery/phase-04-live-site-provenance-ux.md) |
| Phase 6 — Deterministic claim candidates and bounded model selection | Complete; deterministic selector retained | [phase-06-deterministic-claim-selection.md](phase-06-deterministic-claim-selection.md) | [../delivery/phase-06-deterministic-claim-selection.md](../delivery/phase-06-deterministic-claim-selection.md) |
| Phase 9 — GPT-OSS quality and stability comparison | Complete; `no-stable-material-uplift` | [phase-09-gpt-oss-quality-decision.md](phase-09-gpt-oss-quality-decision.md) | [../delivery/phase-09-gpt-oss-quality-comparison.md](../delivery/phase-09-gpt-oss-quality-comparison.md) |
| Phase 10 — Deterministic previous-hour comparison engine | Complete; exact-hour deterministic comparison evidence | [phase-10-previous-hour-comparison.md](phase-10-previous-hour-comparison.md) | [../delivery/phase-10-previous-hour-comparison.md](../delivery/phase-10-previous-hour-comparison.md) |
| Phase 11 — Deterministic temporal visualisation | Complete; offline deterministic temporal evidence/rendering proof | [phase-11-deterministic-temporal-visualisation.md](phase-11-deterministic-temporal-visualisation.md) | [../delivery/phase-11-deterministic-temporal-visualisation.md](../delivery/phase-11-deterministic-temporal-visualisation.md) |

Phase 10 compares one current repository-owned snapshot with its uniquely resolved immediate predecessor under the frozen exact `3,600`-second, no-skip/no-fallback contract. Phase 11 consumes that evidence offline to produce canonical temporal history and deterministic reviewer-visible rendering while preserving explicit gaps, ambiguity, side-specific degraded evidence and exact identity continuity.

Neither Phase 10 nor Phase 11 is integrated as a causal dependency of the active report/site/publication path. Phase 12 is limited to establishing honest future operational cadence-bucket evidence and grants no publication authority.

## Superseded active direction

| Phase | Status | Planning record | Evidence |
| --- | --- | --- | --- |
| Phase 5 — Governed LLM analysis | Research and evaluation complete; full-plan model path superseded by Phase 6 | [phase-05-governed-llm-analysis.md](phase-05-governed-llm-analysis.md) | [Phase 5 evaluation history](../../evaluation/phase-05/README.md) |

Phase 5 implemented the evidence bundle, semantic claim-plan contracts, fail-closed validator, deterministic renderer and protected evaluation machinery. No model was selected and automatic generation was not authorised. Corrective run `29285569716` showed that the remaining full-plan model responsibility was still too broad, so the pending GPT-5.6/Nex calibration was cancelled in favour of deterministic candidate compilation and bounded selection.

The chronology and lessons remain recorded in:

- [`../../evaluation/phase-05/semantic-model-evaluation-retrospective.md`](../../evaluation/phase-05/semantic-model-evaluation-retrospective.md);
- [`../../evaluation/phase-05/corrective-screen-29285569716.md`](../../evaluation/phase-05/corrective-screen-29285569716.md).

## Backlog

Ideas that are useful but not ready for the active Phase 12 evidence prerequisite are parked in:

```text
backlog.md
```

Use the backlog to preserve follow-on ideas without expanding Phase 12 into a comparison consumer, site integration or other successor capability implicitly.

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
