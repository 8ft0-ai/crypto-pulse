# GPT-OSS candidate-selection quality comparison

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the completed Phase 9 GPT-OSS/DeepInfra comparison contract and retained evidence.  
> **Status:** Historical; canonical outcome accepted as `no-stable-material-uplift` and paid workflow archived

Phase 9 compared the deterministic candidate selector with the exact route `openai/gpt-oss-120b` through pinned `deepinfra`. The canonical decision is recorded by issue #389 and acceptance comment `5301261397`.

## Canonical execution

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

GitHub Actions completed the protected workflow successfully. That conclusion records execution success, not a positive quality decision.

## Decisive result

The first Stage A case, `historical-degraded-sparse`, reached the exact governed model/provider route with HTTP 200, one router attempt, no provider fallback and trustworthy usage/cost evidence.

The model returned seven known, unique candidate IDs. Their frozen section mapping was:

```text
market_summary:       1
key_observations:     5
data_quality:         1
```

The retained ranking contract permits at most four `key_observations`. Canonical reconstruction/validation therefore classified the response as `candidate_selection_invalid` / model failure.

Under issue #352, a decisive Stage A model-content or candidate-contract failure immediately stops the remaining experiment and yields `no-stable-material-uplift`. The remaining fourteen calls were correctly left unattempted. Aggregate quality, case-level, stability and incremental-value promotion metrics are therefore not adjudicable and were not threshold-tested or imputed.

`no-stable-material-uplift` authorises **no rerun under Phase 9**. GPT-OSS 120B on pinned DeepInfra is not eligible for an operational selector decision from this programme. The deterministic selector remains the sole active selector.

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

The protected artefact retains the prepared manifest, call schedule, request and HTTP evidence, interpreted routing/usage evidence, attempted/unattempted records, reviewer CSV and deterministic decision input. Raw provider evidence remains protected workflow evidence and is not committed or published.

## Retained source contract

The following source-controlled implementation remains for audit and regression coverage:

- `config/gpt-oss-quality-comparison.yml`;
- `llm_analysis/gpt_oss_quality_comparison.py`;
- `llm_analysis/gpt_oss_quality_comparison_runner.py`;
- Phase 9 comparison, router-evidence and remediation tests;
- the frozen Phase 6 corpus and deterministic ranking contract.

The historical runner commands remain implementation evidence only. They grant no execution authority and must not be used to initiate another Phase 9 provider call.

## Archived execution boundary

The temporary paid workflow `.github/workflows/governed-gpt-oss-quality-comparison.yml` is removed by the Phase 9 archival change. Historical commits, workflow runs, consumed IssueOps records and immutable execution tags remain untouched.

There is no Phase 9 rerun authority, no model promotion, no selector change, no automatic generation, no scheduling and no publication authority from this result. The remaining programme work is the separately reviewed roadmap decision record and Phase 9 close-out.
