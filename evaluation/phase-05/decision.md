# Phase 5 governed LLM model decision

## Decision

**No-go.** Neither evaluated free-model configuration is approved for the Phase 5 production-proof path.

The decision is based on the completed protected workflow run [29142348720](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29142348720), executed from trusted `main` commit `501d1f67852f5e022a4fb5661f2a26adbbe251a8` on 11 July 2026.

This is an operational and provider-policy decision, not a comparative model-quality conclusion. No model response reached the offline validation pipeline, so the run produced no evidence about prose quality, semantic accuracy, prompt-injection resistance, readability, usefulness, latency, token use or output reproducibility.

## Reviewed evidence

The workflow completed successfully as evaluation infrastructure:

- the dispatch was restricted to `main`;
- the fixed corpus hashes were validated;
- five deterministic evidence bundles were prepared;
- the protected environment secret was used only by the comparison step;
- two repeats were attempted for each of five cases and each of two models;
- all 20 planned runs produced a `run-record.json` and `validation-report.json`;
- the aggregate decision and reviewer worksheet were retained as non-published workflow artefacts.

The retained artifact is `governed-llm-evaluation-29142348720-1`, artifact ID `8245573081`, with GitHub digest:

```text
sha256:6632880479ef1883ab9ff6380758cd4a5a091eb4698eacb9a870b97be9b016a8
```

The reviewed aggregate summary has SHA-256:

```text
43de3a619eaf47ecd041eeffa5d599f456a49d06a6653a0cf39beab2c40e993d
```

## Evaluated configurations

Both configurations used:

```text
prompt version:          crypto-market-analysis/v1
analysis schema:         crypto-market-analysis/v1
evidence schema:         crypto-market-evidence-bundle/v1
temperature:             0.2
maximum output tokens:   4000
structured output:       required
zero-data retention:     required
cross-model fallback:    disabled
maximum provider price:  zero
```

| Configuration | Catalogue status | Hard passes | Runtime result |
|---|---:|---:|---|
| `nvidia/nemotron-3-super-120b-a12b:free` | Available, zero-priced, structured-output capable | 0/10 | All 10 requests failed with `ineligible_routing`: no endpoint matched the required zero-data-retention policy. |
| `qwen/qwen3-next-80b-a3b-instruct:free` | Available, zero-priced, structured-output capable; listed expiry 19 July 2026 | 0/10 | All 10 requests failed at the provider boundary. Four returned a generic provider error and six explicitly hit the free-tier eight-requests-per-minute limit. |

No actual serving provider was recorded for either model because no request completed successfully.

## Interpretation

Catalogue eligibility was necessary but insufficient. OpenRouter listed both model slugs with zero pricing and structured-output support, but the runtime constraints prevented either configuration from completing a single governed generation.

For Nemotron, the result is conclusive under the current policy: the free route is not usable while zero-data retention remains mandatory.

For Qwen, the run proves that the evaluated free configuration is not sufficiently reliable for the bounded production-proof path. The rate limit was not an incidental prose-quality defect; provider availability and repeatable execution are hard gates in the source-controlled scoring rubric. The four generic provider failures also prevent a clean partial comparison.

The no-go decision does not assert that either underlying model is intrinsically unsuitable. It rejects the exact evaluated model, provider, pricing and policy configurations.

## Consequences

The repository must not:

- promote either evaluated model as the approved Phase 5 pinned configuration;
- weaken zero-data retention merely to make Nemotron routable;
- enable cross-model fallback;
- adopt a paid model without separate approval;
- enable automatic generation after snapshot merges;
- treat the rolling report workflow as production-approved;
- reuse evaluation output as market evidence.

The existing generation configuration remains source-controlled for experimentation, but it is **not approved for the Phase 5 accepted path**.

Issue #189 is blocked because its acceptance criteria require a successful governed dry run and an accepted rolling report PR. Before #189 can continue, a separate planning decision must approve one of the following:

1. a different explicit model/provider configuration that satisfies ZDR and reliability requirements;
2. a paid routing option with an approved cost boundary;
3. a deliberately revised privacy or provider-policy constraint, subject to separate governance review; or
4. closure of the LLM report path while retaining the deterministic non-LLM product.

## Issue #188 evidence record

```text
Parent issue: #181
Corpus path: evaluation/phase-05/corpus.yml
Snapshots and SHA-256 values: locked in corpus.yml and validated by run 29142348720
Selection rationale: documented per case in corpus.yml
Scoring rubric path: evaluation/phase-05/scoring-rubric.md
Models/configurations evaluated: Nemotron free current candidate; Qwen free alternative
Actual providers observed: none; no request completed successfully
Prompt/schema versions: crypto-market-analysis/v1; crypto-market-evidence-bundle/v1
Hard validation failures: Nemotron 10 ineligible-routing; Qwen 10 provider failures
Usefulness/readability results: unavailable because accepted outputs = 0
Latency/token/cost results: unavailable; recorded estimated cost total = USD 0
Reproducibility observations: repeated provider-boundary failures only; no output reproducibility evidence
Selected pinned configuration or no-go decision: no-go; selected model = none
Evaluation output reused as evidence: no
_site committed: no
```
