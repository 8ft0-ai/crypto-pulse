# Phase 9 GPT-OSS quality comparison

Status: completed historical evaluation. Canonical outcome `no-stable-material-uplift`; paid workflow archived; no Phase 9 rerun authorised.

Parent programme: #352  
Decision issue: #389  
Accepted decision comment: `5301261397`  
Recovery-v4 lifecycle: #386

## Decision question and answer

> Does `openai/gpt-oss-120b` on pinned `deepinfra` provide stable, material incremental candidate-selection value over the deterministic selector across the frozen five-case corpus?

**No under the frozen Phase 9 contract.** The first Stage A call produced a model/candidate-contract failure, which #352 defines as terminal `no-stable-material-uplift`.

Phase 9 reused the frozen Phase 6 corpus and deterministic comparator plus the Phase 8 HTTP-first evidence boundary. It did not rewrite those historical results.

## Frozen execution contract

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

## Canonical protected execution

```text
Dispatcher run:             31867552577
Protected run:              31867564494
Trusted SHA:                43c69ed122c4e39cf2dda92bfcefa7e4314b3922
Run attempt:                1
Outcome:                    no-stable-material-uplift
Status:                     partial-non-adjudicable
Attempted paid calls:       1
Accepted calls:             0
Unattempted calls:          14
Observed total cost:        USD 0.000953014
```

The first call for `historical-degraded-sparse` completed the exact GPT-OSS/DeepInfra route with HTTP 200, one router attempt, no provider fallback, zero retries and zero semantic repairs. The returned envelope contained seven valid candidate IDs, but their frozen section mapping contained five `key_observations`; the ranking contract permits at most four. Canonical reconstruction/validation therefore classified the response as a model-content/candidate-contract failure.

The runner stopped immediately as required. Four later Stage A calls and all ten Stage B calls remained unattempted. Incomplete-corpus aggregate quality, case-level, stability and incremental-value promotion metrics remain `not_adjudicable`; no missing call is imputed as an empty selection.

## Retained evidence

Prepared artefact:

```text
ID:      9242467310
Digest:  sha256:69eef6f0989a61865e59210e97ec7187865243834cc1cee014013eff441a42f8
```

Protected comparison artefact:

```text
ID:      9242498501
Digest:  sha256:4664e6dbff016aad2e60473728545ee08f9da5094f5ca79b8cea766e4fa8b073
```

The protected evidence retains the regenerated deterministic comparator, exact planned/attempted/unattempted schedule, HTTP-first response observations, router/model/provider identity, usage/cost evidence, failure classification, reviewer CSV and deterministic decision input. Raw provider responses remain protected evidence and are not committed or published.

## Archived execution boundary

The temporary paid workflow `.github/workflows/governed-gpt-oss-quality-comparison.yml` has been removed from executable `main` by the Phase 9 archival change. The comparison configuration, runner, scoring implementation, frozen corpus and regression tests remain source-controlled for audit.

Consumed IssueOps records and immutable execution tags remain historical evidence and are not edited by archival. Their exact source commits retain the original protected workflow bytes and hashes.

There is **no rerun** authorised under Phase 9. No recovery-v5, provider/model promotion, selector change, automatic generation, scheduling, repository write or publication follows from this outcome. The deterministic selector remains the sole active selector.

The remaining lifecycle work is a separately reviewed roadmap decision record followed by Phase 9 close-out after archival and decision evidence reconcile.
