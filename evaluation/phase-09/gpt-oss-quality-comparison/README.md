# Phase 9 GPT-OSS quality comparison

Status: implementation pending independent review and merge. No provider call is authorised by this directory.

Issue: #352
Validated issue comment: `5173267796`

## Decision question

> Does `openai/gpt-oss-120b` on pinned `deepinfra` provide stable, material incremental candidate-selection value over the deterministic selector across the frozen five-case corpus?

This implementation reuses the frozen Phase 6 corpus and deterministic comparator, and the Phase 8 HTTP-first response evidence boundary. It does not rewrite either historical result.

## Fixed execution

```text
Stage A:                    one sequential call per case, five maximum
Stage B:                    two repeat-major rounds, ten maximum
Total paid calls:           15 maximum
Model:                      openai/gpt-oss-120b
Provider only:              deepinfra
Provider fallback:          disabled
Cross-model fallback:       disabled
Semantic repairs:           0
Network retries:            0
Route probes:               0
Per-call ceiling:           USD 0.005
Whole-run ceiling:          USD 0.075
```

Preparation regenerates the five cases, deterministic baseline, canonical candidate sets and candidate-ID requests without a provider secret. It resolves the two frozen required-expectation subsets to unique candidate IDs and hashes those ordered sets before protected execution.

The runner stops after the first decisive failure. Model/content failures produce `no-stable-material-uplift`; route, identity, catalogue, metering, evidence or cost-governance failures produce `inconclusive-infrastructure`. Only fifteen accepted calls allow full quality, stability and incremental-value adjudication.

## Evidence

The protected artefact retains:

- the exact prepared manifest and deterministic comparator;
- catalogue eligibility and price evidence;
- every planned, attempted and unattempted call;
- request hashes and sanitised HTTP observations written before interpretation;
- actual model/provider and one-attempt routing evidence;
- usage, reasoning-token count, finish reason, latency and cost;
- selected IDs, validation, reconstructed plans and deterministic renders;
- count-first quality metrics;
- pairwise Jaccard and stable-majority evidence;
- additions/losses and required-candidate coverage;
- reviewer CSV and deterministic decision input.

Raw provider responses remain protected workflow artefacts and are never committed or published.

## Operational boundary

Even `eligible-for-operational-decision` only permits a separately reviewed operational decision. The workflow cannot alter candidate ranking, enable model selection, mutate a branch, generate or publish reports, schedule execution or replace the deterministic selector.
