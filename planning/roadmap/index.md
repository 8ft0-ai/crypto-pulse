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

## Active roadmap specs

| Phase | Status | Planning record | Delivery record |
| --- | --- | --- | --- |
| Phase 4 — Live-site provenance UX | Shaping | [phase-04-live-site-provenance-ux.md](phase-04-live-site-provenance-ux.md) | Pending |

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
