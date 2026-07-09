# CryptoPulse roadmap

This directory records the delivery phases for CryptoPulse in a way that is easier to read than reconstructing the project history from issues, pull requests, workflow runs, and comments alone.

The issue and pull-request history remains the audit trail. These roadmap files are a retrospective and forward-looking management layer over that history.

## Phase-pack operating model

Future phases should use a small phase pack:

```text
phase spec in docs/roadmap/     -> intent, scope, risks, and definition of done
parent phase issue              -> delivery control and linked-work checklist
linked child issues             -> executable work breakdown
pull requests                   -> implementation and validation evidence
close-out comments              -> final proof trail
```

Native GitHub sub-issues are optional. The connector can create and update issues, but cannot reliably create native sub-issue relationships, so parent/child structure should be explicit in Markdown and issue bodies.

## Completed phases

| Phase | Status | Primary outcome | Phase record |
| --- | --- | --- | --- |
| Phase 1 — Source evidence spine | Complete | Scheduled ingestion can produce a scoped `valid-ok` source snapshot PR. | [phase-01-source-evidence-spine.md](phase-01-source-evidence-spine.md) |
| Phase 2 — Deterministic report review loop | Complete | A merged `valid-ok` source snapshot can produce a reviewed deterministic Markdown report PR and be rendered by the static site generator without committing `_site/`. | [phase-02-deterministic-report-review-loop.md](phase-02-deterministic-report-review-loop.md) |

## Next phase direction

Phase 3 should make generated report PRs self-proving before they are opened. The motivation comes from Phase 2: generated PRs created by GitHub Actions with `GITHUB_TOKEN` can leave downstream PR validation in an approval-required state, so the generating workflow should run the critical proof steps itself before creating the PR.

## Delivery ledger

For a concise chronological ledger of completed phases, see:

```text
docs/delivery-log.md
```
