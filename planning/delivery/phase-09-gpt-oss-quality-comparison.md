# Phase 9 — GPT-OSS quality and stability comparison

Status: complete.

## Outcome

Phase 9 tested whether `openai/gpt-oss-120b` on pinned `deepinfra` could provide stable, material incremental candidate-selection value over the retained deterministic selector across the frozen five-case corpus.

The accepted canonical outcome is:

```text
no-stable-material-uplift
```

The first Stage A provider-facing call reached the exact governed model/provider route successfully, but the returned selection violated the frozen candidate-section contract during canonical reconstruction and validation. Five selected IDs mapped to `key_observations`, where the frozen maximum is four. Under the predeclared Phase 9 outcome mapping, that model-content/candidate-contract failure is terminal and is not an infrastructure failure.

GPT-OSS 120B on pinned DeepInfra is therefore not eligible for an operational selector decision under Phase 9. No model or provider is promoted, no selector is changed, and no further Phase 9 run or recovery-v5 is authorised. The deterministic selector remains the sole active selector.

## Delivery scope

Parent issue: #352  
Implementation PR: #355  
Reusable IssueOps dispatcher contract: #356  
Protected-execution governance and hardening: #358, #359, #360, #362, #363, #364  
Corrective recovery lifecycles: #368, #376, #378, #386  
Representative provenance/router remediations: #366, #374, #380, #382  
Canonical decision: #389  
Paid-workflow archival: #390 / PR #391  
Roadmap decision record: #392 / PR #394  
Delivery close-out: #395

The implementation established a Phase 9-specific, candidate-ID-only comparison boundary over the unchanged five-case Phase 6 corpus. It retained exact model/provider identity, zero provider fallback, zero cross-model fallback, zero network retries, zero semantic repairs, zero route probes, fixed call and cost ceilings, evidence-first retention, deterministic reconstruction and rendering, and explicit fail-closed outcome classes.

The protected execution path added reusable IssueOps controls and trusted-main provenance enforcement so one-time execution authority could be consumed without weakening the target workflow's model, evidence, cost or rerun controls. Infrastructure defects encountered during earlier attempts were separately diagnosed and remediated without changing the frozen quality gates. Each consumed authority remained one-time and non-reusable.

## Canonical protected execution

```text
Dispatcher run:            31867552577
Protected run:             31867564494
Trusted execution SHA:     43c69ed122c4e39cf2dda92bfcefa7e4314b3922
Protected run attempt:     1
Outcome:                   no-stable-material-uplift
Status:                    partial-non-adjudicable
Planned paid calls:        15
Attempted paid calls:      1
Accepted calls:            0
Unattempted calls:         14
Observed total cost:       USD 0.000953014
Network retries:           0
Semantic repairs:          0
Route probes:              0
```

GitHub Actions completed the protected workflow successfully. That workflow conclusion records successful execution of the governed workflow; it is not a positive model-quality result.

The attempted case was `historical-degraded-sparse`. The retained route evidence established:

```text
Requested model:           openai/gpt-oss-120b
Actual model:              openai/gpt-oss-120b
Required provider:         deepinfra
Selected provider:         DeepInfra
Router attempts:           1
Provider fallback:         none
HTTP/provider execution:   successful
```

The returned envelope contained seven known, unique candidate IDs. Their frozen section mapping was one `market_summary`, five `key_observations` and one `data_quality`. The candidate-selection contract permits at most four `key_observations`, so canonical reconstruction/validation classified the response as `candidate_selection_invalid` / model failure.

That classification is model-content/candidate-contract failure. It is not a route, provider, model-identity, catalogue, metering, evidence-capture, protected-execution or cost-governance failure.

## Non-adjudicable promotion metrics

The fail-closed stop after the first decisive Stage A failure left fourteen calls unattempted. The incomplete corpus therefore cannot support completed-corpus promotion adjudication.

Aggregate quality, case-level protection, stability, stable-majority and incremental-value gates remain:

```text
partial-non-adjudicable / not_adjudicable
```

No unattempted call is imputed as an empty selection. Missing metrics are not compared with promotion thresholds, and no partial diagnostic result is promoted into a completed-corpus conclusion.

The overall Phase 9 outcome is nevertheless decisive because #352 explicitly maps an attempted model-content/candidate-contract failure to `no-stable-material-uplift`.

## Retained protected evidence

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

The retained evidence preserves the prepared comparator and call schedule, request and HTTP observations, model/provider routing evidence, metering and cost evidence, attempted/unattempted records, failure classification and reviewer material. Raw provider responses remain protected workflow evidence and are not committed or published.

Historical consumed IssueOps records and immutable execution tags remain part of the canonical audit trail. They are not edited, reset, reused or deleted by close-out.

## Final decision and workflow archival

The accepted final decision is recorded in:

```text
planning/roadmap/phase-09-gpt-oss-quality-decision.md
```

The temporary paid execution workflow:

```text
.github/workflows/governed-gpt-oss-quality-comparison.yml
```

was archived from executable `main` by #390 / PR #391 after the canonical decision was accepted. Source-controlled Phase 9 configuration, runners, scoring implementation, frozen corpus, deterministic selector, regression/remediation tests, historical commits and protected evidence remain retained for audit.

The durable roadmap decision was merged by #392 / PR #394 as merge commit:

```text
73b3cf203bf9a81b1b9fa3d61c47c99f95da5a2c
```

## Operating position after Phase 9

- `openai/gpt-oss-120b` on pinned `deepinfra` is not promoted or enabled.
- Deterministic candidate selection remains the sole active selector.
- No Phase 9 rerun or recovery-v5 is authorised.
- No provider/model fallback, repair or retry is introduced from this result.
- Automatic report generation, scheduling and publication remain disabled.
- No model-authored claims, evidence, values, rationale or prose are enabled.
- The temporary paid Phase 9 workflow remains absent from executable `main`.
- Historical Phase 9 authority and execution evidence remain immutable audit records.
- Any future model-selection investigation requires a new, separately governed programme with new evidence, budget, acceptance gates and execution authority.

## Validation evidence

The implementation PR #355 received repository-native validation on its exact accepted implementation head before merge. Later remediation and activation candidates were separately validated and reviewed at their own lifecycle gates.

The roadmap decision candidate in PR #394 passed repository-native validation run:

```text
31874177062
```

on exact candidate head:

```text
9c27fa449c9ca744f17ddd0b349683c97532662e
```

before substantive acceptance and merge.

The Phase 9 close-out PR must rerun repository-native credential-free validation on its own exact head. No provider/model invocation is required for close-out validation.

## Boundaries preserved

- The frozen five-case corpus and reviewed-useful manifest remain unchanged.
- The deterministic comparator and selector remain unchanged.
- Phase 9 model/provider, scoring, quality, stability, incremental-value, call and cost contracts are not reinterpreted during close-out.
- Historical consumed IssueOps records and execution tags are not modified.
- No protected workflow is restored, dispatched or rerun.
- No provider/model is invoked by close-out.
- Automatic generation, scheduling and publication remain disabled.
- Generated `_site/` output remains disposable and uncommitted.

## Delivery graph decision

Delivery graph update: N/A.

Phase 9 is a bounded evaluation and governance programme. It does not add a new production pipeline stage, committed report artefact, deployed service, source-ingestion dependency or publication path. Its terminal outcome retains the already-active deterministic selector and archives the temporary paid workflow. Modelling the implementation, IssueOps hardening, corrective recovery lifecycles and protected attempts as graph nodes would turn the compact causal graph into an execution inventory.

Phase 9 is therefore represented in this delivery record and `planning/delivery-log.md`; `planning/delivery/delivery.yaml` and generated `planning/delivery/graph.md` remain unchanged under the established compact graph-modelling rules.

## Carry-forward lessons

1. Keep model authority structurally narrow: candidate IDs only, with repository-owned reconstruction, validation and rendering.
2. Freeze outcome classes and quality gates before paid execution so a terminal content failure cannot be reinterpreted after the fact.
3. Treat provenance and routing evidence as first-class governed data, and remediate infrastructure defects without changing the experiment's quality contract.
4. Consume protected execution authority once and preserve immutable tags and historical records rather than reusing failed authorities.
5. Stop immediately on a decisive model-content/candidate-contract failure; do not spend the remaining call budget for diagnostic curiosity.
6. Keep incomplete-corpus promotion metrics explicitly non-adjudicable rather than imputing missing calls.
7. Archive temporary paid workflow entry points once the decision is terminal while retaining the implementation and evidence required for audit.
