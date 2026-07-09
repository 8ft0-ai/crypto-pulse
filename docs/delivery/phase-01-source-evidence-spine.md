# Phase 1 — Source evidence spine

Status: complete.

This is a post-delivery record. It does not replace the original issue, pull-request, workflow-run, commit, or evidence-comment history.

## Primary outcome

Scheduled ingestion can produce a scoped `valid-ok` source snapshot PR.

Phase 1 established the source-evidence spine for CryptoPulse: the repository can archive crypto source snapshots as raw evidence under `data/crypto/hourly/...`, validate the snapshot, and review the generated source package through a scoped pull request.

The most concrete proof point carried forward is PR #89, which added the merged `valid-ok` source snapshot later used by Phase 2.

## Parent issue

```text
#75 — Build source evidence v1 and deterministic report spine
```

## Linked issues / work breakdown

```text
#76, #77, #78, #79, #80, #81, #82
```

## Key PRs

```text
#89 — Add crypto source snapshot 1742_AEST_source_snapshot
```

## Final proof evidence

```text
Source snapshot PR: #89
Source snapshot workflow run: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28926128310
Source snapshot path: data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
Snapshot quality: valid-ok
Required sources: coingecko, defillama
Selected exchange cross-check: coinbase_exchange
Source snapshot PR merge commit: 178703aef4be8fc0ecf35677e1ffeffe7d4d4a52
_site committed: no
```

## Produced artefacts

```text
data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

## Validation evidence

- Source data was captured as an auditable snapshot.
- Snapshot validation classified source quality before downstream report generation.
- The source snapshot PR was scoped to `data/crypto/hourly/...`.
- Required source status and selected exchange cross-check were recorded.
- Disabled or unavailable sources were recorded rather than hidden.

## Boundaries preserved

- No Markdown market report was generated as part of the source snapshot PR.
- No LLM call was required for source ingestion.
- No generated `_site/` output was committed.
- No secrets or paid API keys were introduced.

## Carry-forward lesson

Phase 1 created the evidence input that Phase 2 needed. Future phases should continue to treat source snapshots as immutable archived evidence and should avoid mixing source ingestion, report generation, and site publication into one opaque step.

## Follow-on phase

Phase 2 used the merged `valid-ok` source snapshot from PR #89 to prove deterministic report generation, generated report validation, PR evidence, and static-site rendering.
