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

There is no active implementation phase. Phase 10 is the sole owner-approved shaping candidate after the Phase 9 close-out. Its roadmap specification records the bounded deterministic direction only; implementation requires a separate delivery-control issue and separate owner authority.

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 10 — Deterministic previous-hour comparison engine | Shaping; planning only under #398 | [phase-10-previous-hour-comparison.md](phase-10-previous-hour-comparison.md) | Pending |

Phase 10 extends the repository-owned evidence path before any model or narrative layer: compare a current validated snapshot with one uniquely resolved valid predecessor, emit deterministic structured change evidence, and fail closed when continuity or comparability cannot be proved.

## Completed roadmap directions

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 4 — Live-site provenance UX | Implementation complete | [phase-04-live-site-provenance-ux.md](phase-04-live-site-provenance-ux.md) | [../delivery/phase-04-live-site-provenance-ux.md](../delivery/phase-04-live-site-provenance-ux.md) |
| Phase 6 — Deterministic claim candidates and bounded model selection | Complete; deterministic selector retained | [phase-06-deterministic-claim-selection.md](phase-06-deterministic-claim-selection.md) | [../delivery/phase-06-deterministic-claim-selection.md](../delivery/phase-06-deterministic-claim-selection.md) |
| Phase 9 — GPT-OSS quality and stability comparison | Complete; `no-stable-material-uplift` | [phase-09-gpt-oss-quality-decision.md](phase-09-gpt-oss-quality-decision.md) | [../delivery/phase-09-gpt-oss-quality-comparison.md](../delivery/phase-09-gpt-oss-quality-comparison.md) |

The deterministic selector delivered in Phase 6 remains the sole active selector. Phase 9 did not promote a model or provider, authorise another Phase 9 run, or enable automatic generation, scheduling or publication. Its temporary paid comparison workflow remains archived from executable `main`.

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

Use the backlog to preserve follow-on ideas without expanding the current shaping scope.

## Retrospective roadmap specs

Phases 1–3 were reconstructed after delivery to preserve the intended roadmap shape alongside the completed delivery records.

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 1 — Source evidence spine | Delivered; retrospective roadmap spec | [phase-01-source-evidence-spine.md](phase-01-source-evidence-spine.md) | [../delivery/phase-01-source-evidence-spine.md](../delivery/phase-01-source-evidence-spine.md) |
| Phase 2 — Deterministic report review loop | Delivered; retrospective roadmap spec | [phase-02-deterministic-report-review-loop.md](phase-02-deterministic-report-review-loop.md) | [../delivery/phase-02-deterministic-report-review-loop.md](../delivery/phase-02-deterministic-report-review-loop.md) |
| Phase 3 — Self-proving generated report PRs | Delivered; retrospective roadmap spec | [phase-03-self-proving-generated-report-prs.md](phase-03-self-proving-generated-report-prrs.md) | [../delivery/phase-03-self-proving-generated-report-prs.md](../delivery/phase-03-self-proving-generated-report-prs.md) |

## Delivery records

For completed phase records, see:

```text
../delivery/index.md
```

For the concise chronological ledger, see:

```text
../delivery-log.md
```
