# CryptoPulse roadmap

This directory contains active and future planning records for CryptoPulse delivery phases.

The issue and pull-request history remains the audit trail. Roadmap documents should explain intended work before delivery. Completed phase evidence belongs in `docs/delivery/`, with `docs/delivery-log.md` retained as the concise chronological ledger.

## Planning versus delivery

```text
docs/roadmap/  -> active or future phase planning
docs/delivery/ -> completed phase close-out records
docs/delivery-log.md -> concise chronological ledger
```

## Phase-pack operating model

Future phases should use a small phase pack:

```text
phase spec in docs/roadmap/     -> intent, scope, risks, and definition of done
parent phase issue              -> delivery control and linked-work checklist
linked child issues             -> executable work breakdown
pull requests                   -> implementation and validation evidence
close-out comments              -> final proof trail
completed record in docs/delivery/ -> post-delivery close-out artefact
```

Native GitHub sub-issues are optional. The connector can create and update issues, but cannot reliably create native sub-issue relationships, so parent/child structure should be explicit in Markdown and issue bodies.

## Future phase template

Use the template when shaping a new phase:

```text
phase-template.md
```

A new roadmap phase spec should stay forward-looking. At close-out, move the completed evidence into `docs/delivery/` and keep the roadmap directory focused on active/future planning.

## Completed phases

| Phase | Status | Primary outcome | Delivery record |
| --- | --- | --- | --- |
| Phase 1 — Source evidence spine | Complete | Scheduled ingestion can produce a scoped `valid-ok` source snapshot PR. | [../delivery/phase-01-source-evidence-spine.md](../delivery/phase-01-source-evidence-spine.md) |
| Phase 2 — Deterministic report review loop | Complete | A merged `valid-ok` source snapshot can produce a reviewed deterministic Markdown report PR and be rendered by the static site generator without committing `_site/`. | [../delivery/phase-02-deterministic-report-review-loop.md](../delivery/phase-02-deterministic-report-review-loop.md) |
| Phase 3 — Self-proving generated report PRs | Complete | Generated report PRs carry their own pre-PR proof, with downstream PR validation retained as defence in depth. | [../delivery/phase-03-self-proving-generated-report-prs.md](../delivery/phase-03-self-proving-generated-report-prs.md) |

## Delivery records

For completed phase records, see:

```text
../delivery/index.md
```

For a concise chronological ledger, see:

```text
../delivery-log.md
```
