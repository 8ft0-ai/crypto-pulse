# Phase 1 — Source evidence spine

Status: delivered; retrospective roadmap spec.

This is a reconstructed forward-looking roadmap spec. It describes the planning intent that Phase 1 served before the completed delivery evidence was recorded.

## Problem statement

CryptoPulse needed an auditable source-evidence foundation before it could generate or review market reports.

Without a validated source snapshot, downstream report generation would have no stable evidence boundary. A generated report could mix data collection, interpretation, site rendering, and publication in one opaque step, making review difficult and making it unclear which source state had produced a report.

## Goal

Prove that scheduled ingestion can produce a scoped `valid-ok` source snapshot PR.

The phase should establish source snapshots as immutable evidence under `data/crypto/hourly/...`, with enough validation metadata to support later deterministic report generation.

## Non-goals

Phase 1 should not introduce:

- generated Markdown market reports;
- static-site rendering or publication;
- committed `_site/` output;
- LLM-generated report narrative;
- investment advice, trading recommendations, trading signals, target prices, or position guidance;
- secrets or paid API keys;
- auto-merge or auto-publish.

## Target workflow or target state

```text
fetch source data
validate source snapshot
record source quality and source status
create automation branch
commit only data/crypto/hourly/... snapshot evidence
open scoped source snapshot PR
review and merge the source snapshot PR
```

## Acceptance gates

Phase 1 is complete when:

- [x] the ingestion workflow can fetch crypto source data;
- [x] a snapshot can be validated and marked `valid-ok`;
- [x] required source status is recorded;
- [x] optional exchange cross-check status is recorded where available;
- [x] disabled, unavailable, or warning sources are visible rather than hidden;
- [x] the generated PR commits only `data/crypto/hourly/...`;
- [x] no generated `_site/` output is committed;
- [x] the merged snapshot can be used as stable evidence for later phases.

## Proposed implementation slices

```text
1. Define the source snapshot shape and validation expectations.
2. Implement scheduled ingestion and source capture.
3. Validate required and optional source status.
4. Scope automation branch and PR changes to source snapshot files.
5. Prove the ingestion flow with a real valid-ok snapshot PR.
6. Record close-out evidence for the phase.
```

## Risks and mitigations

### Risk: Source capture and report generation become coupled

Mitigation: keep Phase 1 scoped to source snapshots only. Reports should be generated in a later phase from a merged snapshot.

### Risk: A snapshot looks valid but hides missing source quality

Mitigation: require validation metadata for required sources, optional exchange sources, disabled sources, warnings, and blocking issues.

### Risk: Generated site output leaks into source evidence PRs

Mitigation: keep generated `_site/` output out of the ingestion commit scope.

## Definition of done

The phase is complete when a real source snapshot PR is merged and the delivery record captures:

```text
Parent issue
Linked issues
Proof PR
Workflow run
Snapshot path
Snapshot quality
Required sources
Selected exchange cross-check
Merge commit
_site committed: no
```

## Follow-on delivery record

Completed evidence is recorded in:

```text
planning/delivery/phase-01-source-evidence-spine.md
```

## Follow-on phase

Phase 2 should use a merged `valid-ok` source snapshot to prove deterministic Markdown report generation and static-site rendering without committing `_site/`.
