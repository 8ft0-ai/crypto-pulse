# Phase 9 — GPT-OSS quality and stability decision

Status: approved.  
Decision date: 2026-08-15.  
Decision issue: #389  
Roadmap record issue: #392  
Phase contract: #352  
Recovery-v4 lifecycle: #386

## Decision

The Phase 9 decision question is answered **no stable material uplift**:

> Does `openai/gpt-oss-120b` on pinned `deepinfra` provide stable, material incremental candidate-selection value over the deterministic selector across the frozen five-case corpus?

The accepted canonical outcome is:

```text
no-stable-material-uplift
```

The first Stage A call reached the exact governed GPT-OSS/DeepInfra route successfully, but the returned candidate selection violated the frozen candidate-section contract during canonical reconstruction/validation. Under the predeclared Phase 9 outcome mapping in #352, that model-content/candidate-contract failure is terminal and yields `no-stable-material-uplift`.

GPT-OSS 120B on pinned DeepInfra is therefore **not eligible for an operational selector decision under Phase 9**. No model/provider promotion or selector change follows from this result. The deterministic selector remains the sole active selector.

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

GitHub Actions completed the protected workflow successfully. That workflow conclusion records execution success; it is not a positive Phase 9 quality result.

## Decisive Stage A evidence

The first case was `historical-degraded-sparse`.

```text
Requested model:           openai/gpt-oss-120b
Actual model:              openai/gpt-oss-120b
Required provider:         deepinfra
Selected provider:         DeepInfra
Router attempts:           1
Provider fallback:         none
HTTP/provider execution:   successful
Network retries:           0
Semantic repairs:          0
Route probes:              0
```

The model returned seven known, unique candidate IDs. Their frozen section mapping was:

```text
market_summary:       1
key_observations:     5
data_quality:         1
```

The retained candidate-selection contract permits at most four `key_observations`. Canonical reconstruction/validation therefore classified the response as `candidate_selection_invalid` / model failure.

This is a model-content/candidate-contract failure. It is not a route, provider, model-identity, catalogue, metering, evidence-capture, protected-execution or cost-governance failure.

## Outcome mapping

Issue #352 fixed the Phase 9 stop rule before execution:

- a model-content, candidate-contract, reconstruction, semantic-validation, rendering, prompt-injection or safety failure yields `no-stable-material-uplift`;
- an infrastructure, route, provider, model-identity, catalogue, price, metering, evidence-capture, protected-execution or cost-governance failure yields `inconclusive-infrastructure`.

Because the first Stage A call failed the frozen candidate contract after successful exact-route execution, the correct outcome is `no-stable-material-uplift`.

The runner stopped immediately as required. Four later Stage A calls and all ten Stage B calls remained unattempted.

## Non-adjudicable promotion metrics

The incomplete corpus cannot support completed-corpus promotion adjudication. Aggregate quality, case-level protection, stability, stable-majority and incremental-value gates remain:

```text
partial-non-adjudicable / not_adjudicable
```

No unattempted call is imputed as an empty selection. No missing metric is compared with a promotion threshold, and no partial diagnostic score is promoted into a completed-corpus conclusion.

The overall Phase 9 outcome nevertheless remains decisive because #352 explicitly maps this attempted model-content/candidate-contract failure to `no-stable-material-uplift`.

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

The protected evidence retains the prepared comparator and call schedule, request and HTTP observations, model/provider routing evidence, metering and cost evidence, attempted/unattempted records, failure classification, reviewer material and deterministic decision input. Raw provider responses remain protected workflow evidence and are not committed or published.

## No-rerun boundary

`no-stable-material-uplift` authorises **no further Phase 9 rerun**.

There is no recovery-v5 authority and no basis under #352 for another corrective Phase 9 execution lifecycle. The separately reviewed recovery-v4 authority is consumed historical evidence and is not reusable.

Any future model-selection investigation would require a new, separately governed programme with new evidence, budget, acceptance gates and execution authority. It cannot reuse Phase 9 authority or reinterpret this outcome as infrastructure-inconclusive.

## Archived execution boundary

The temporary paid workflow:

```text
.github/workflows/governed-gpt-oss-quality-comparison.yml
```

was archived from executable `main` by #390 / PR #391 after the canonical decision was accepted. Historical commits, workflow runs, consumed IssueOps records and immutable execution tags remain retained as audit evidence and are not rewritten by archival.

The source-controlled Phase 9 configuration, runner, scoring implementation, frozen corpus, deterministic selector and regression/remediation tests remain retained for audit.

## Operational consequences

- GPT-OSS 120B on pinned DeepInfra is not promoted or enabled.
- Deterministic candidate selection remains the sole active selector.
- No Phase 9 rerun or recovery-v5 is authorised.
- No provider or model fallback, repair or retry is introduced from this result.
- Automatic report generation, scheduling and publication remain disabled.
- No model-authored claims, evidence, values, rationale or prose are enabled.
- The archived paid workflow remains absent from executable `main`.
- Historical Phase 9 authority and execution evidence remain immutable audit records.

## Close-out boundary

This roadmap record satisfies the Phase 9 requirement to record the accepted final outcome durably. It does not itself close #352, #386 or #389 and does not perform delivery close-out.

Phase 9 may be closed only through a subsequent reconciliation gate that confirms implementation, protected execution, canonical decision, workflow archival and this roadmap record all agree, and updates any required delivery-control records under the repository close-out discipline.