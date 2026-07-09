# Phase 1 — Source evidence spine

Status: complete.

This is a retrospective record. It does not replace the original issue, pull-request, or workflow history.

## Outcome

Phase 1 established the source-evidence spine for CryptoPulse: the repository can archive crypto source snapshots as raw evidence under `data/crypto/hourly/...`, validate the snapshot, and review the generated source package through a scoped pull request.

The most concrete proof point now carried forward is PR #89, which added the merged `valid-ok` source snapshot later used by Phase 2.

## Key evidence

```text
Source snapshot PR: #89
Source snapshot workflow run: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28926128310
Source snapshot path: data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
Snapshot quality: valid-ok
Required sources: coingecko, defillama
Selected exchange cross-check: coinbase_exchange
Source snapshot PR merge commit: 178703aef4be8fc0ecf35677e1ffeffe7d4d4a52
```

## What this phase proved

- Source data can be captured as an auditable snapshot.
- Snapshot validation can classify source quality before downstream report generation.
- Snapshot PRs can be scoped to `data/crypto/hourly/...`.
- Generated `_site/` output remains out of scope and uncommitted.
- The no-secrets MVP can operate with public/no-key sources and explicitly record disabled or skipped sources.

## Boundaries preserved

- No Markdown market report was generated as part of the source snapshot PR.
- No LLM call was required for source ingestion.
- No generated `_site/` output was committed.
- Disabled or unavailable sources were recorded rather than hidden.

## Carry-forward lesson

Phase 1 created the evidence input that Phase 2 needed. Future phases should continue to treat source snapshots as immutable archived evidence and should avoid mixing source ingestion, report generation, and site publication into one opaque step.

## Follow-on phase

Phase 2 used the merged `valid-ok` source snapshot from PR #89 to prove deterministic report generation, generated report validation, PR evidence, and static-site rendering.
